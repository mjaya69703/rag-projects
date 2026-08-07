"""Vector Store: ChromaDB persistent + embedding lokal MiniLM.

- Embedding model ``paraphrase-multilingual-MiniLM-L12-v2`` di-load sekali
  (lazy singleton) agar hemat RAM.
- ChromaDB persistent di folder ``data/chroma_db``, ruang metrik cosine.
- Metadata tiap chunk: source, page, heading, chunk_index.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.hybrid_search import HybridSearch
from app.pdf_parser import Chunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_PERSIST_DIR = "data/chroma_db"
DEFAULT_COLLECTION = "documents"
DEFAULT_TOP_K = 5

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load embedding model sekali saja (singleton, lazy)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def unload_model() -> None:
    """Bebaskan model embedding dari memori (hemat RAM idle)."""
    global _model
    _model = None
    import gc

    gc.collect()


def _slug(name: str) -> str:
    """Normalisasi nama file agar aman dipakai sebagai ID ChromaDB."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


class VectorStore:
    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        # Index BM25 lazy untuk hybrid search; di-invalidate saat mutasi.
        self._hybrid = HybridSearch(self)

    @property
    def model(self) -> SentenceTransformer:
        """Model embedding — dimuat saat pertama kali dipakai, bukan di init."""
        return _get_model()

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------
    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed chunk dokumen untuk indexing."""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def _embed_query(self, query: str) -> list[float]:
        """Embed satu pertanyaan."""
        embedding = self.model.encode([query], normalize_embeddings=True)[0]
        return embedding.tolist()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def add_documents(self, chunks: Iterable[Chunk], source: str) -> int:
        """Embed & simpan chunk ke ChromaDB. Return jumlah chunk tersimpan."""
        chunk_list = list(chunks)
        if not chunk_list:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        for chunk in chunk_list:
            meta = chunk.metadata
            idx = meta.get("chunk_index", len(ids))
            ids.append(f"{_slug(meta.get('source') or source)}_chunk_{idx}")
            documents.append(chunk.text)
            metadatas.append(
                {
                    "source": meta.get("source") or source,
                    "page": meta.get("page"),
                    "heading": meta.get("heading", ""),
                    "chunk_index": idx,
                }
            )

        embeddings = self._embed_documents(documents)
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        self._hybrid.invalidate()
        return len(ids)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: dict | None = None,
        hybrid: bool = True,
    ) -> list[dict]:
        """Cari chunk paling relevan (hybrid BM25+vector bila tersedia).

        Hybrid diutamakan: istilah eksak yang lemah di embedding tetap
        ketemu lewat BM25. Kalau rank_bm25 tidak terinstall, fallback ke
        vector-only (perilaku lama).
        """
        if hybrid:
            results = self._hybrid.search(query, top_k=top_k, where=where)
            if results is not None:
                return results

        embedding = self._embed_query(query)
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self.collection.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0] or []
        metadatas = (result.get("metadatas") or [[]])[0] or []
        distances = (result.get("distances") or [[]])[0] or []

        results: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances, strict=True):
            results.append(
                {"text": doc, "metadata": meta, "distance": float(dist)}
            )
        return results

    # ------------------------------------------------------------------
    # Manajemen dokumen
    # ------------------------------------------------------------------
    def list_documents(self) -> list[dict]:
        """Ringkasan dokumen terindeks: jumlah chunk & daftar halaman."""
        result = self.collection.get(include=["metadatas"])
        sources: dict[str, dict] = {}
        for meta in result.get("metadatas") or []:
            src = meta.get("source", "unknown")
            entry = sources.setdefault(src, {"chunks": 0, "pages": set()})
            entry["chunks"] += 1
            if meta.get("page") is not None:
                entry["pages"].add(meta["page"])
        return [
            {"source": src, "chunks": v["chunks"], "pages": sorted(v["pages"])}
            for src, v in sorted(sources.items())
        ]

    def delete_document(self, source: str) -> int:
        """Hapus semua chunk milik satu dokumen. Return jumlah terhapus."""
        result = self.collection.get(where={"source": source}, include=[])
        ids = result.get("ids") or []
        if ids:
            self.collection.delete(ids=ids)
            self._hybrid.invalidate()
        return len(ids)

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        """Hapus semua chunk dokumen (dipakai saat ganti model embedding)."""
        for doc in self.list_documents():
            self.delete_document(doc["source"])

    def close(self) -> None:
        """Tutup koneksi ChromaDB & lepas file lock (penting di Windows)."""
        try:
            self.client.close()
        except Exception:
            logger.warning("Gagal menutup ChromaDB client", exc_info=True)
