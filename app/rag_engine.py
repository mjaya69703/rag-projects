"""RAG Engine: pertanyaan -> retrieve Top-K -> susun prompt -> jawaban LLM + sumber."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.llm_client import LLMClient
from app.semantic_cache import SemanticCache
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Token maksimal untuk jawaban. Bisa di-set via env RAG_MAX_TOKENS.
ANSWER_MAX_TOKENS = int(os.getenv("RAG_MAX_TOKENS", "1024"))

SYSTEM_PROMPT = (
    "Kamu adalah asisten pribadi yang membantu pengguna memahami isi "
    "dokumen-dokumennya. Gaya bicaramu natural dan manusiawi, bukan seperti "
    "laporan mesin. "
    "Aturan: "
    "1. Jawab dalam bahasa yang sama dengan pertanyaan pengguna (Indonesia atau Inggris). "
    "2. Jawab dengan cukup mendalam dan terstruktur: paragraf yang jelas, gunakan "
    "bullet point atau sub-heading hanya jika memudahkan, akhiri dengan kesimpulan "
    "singkat bila jawabannya panjang. JANGAN menjawab terlalu singkat (1-2 kalimat) "
    "kecuali pertanyaannya memang sederhana. "
    "3. Ikuti permintaan panjang/format pengguna (mis. 'tulis 5 paragraf', 'jelaskan "
    "detail', 'buat tabel') selama materinya tersedia di KONTEKS. "
    "4. Hanya gunakan KONTEKS yang diberikan. Jika informasi tidak ada di KONTEKS, "
    "katakan jujur: 'Informasi ini tidak ditemukan di dokumen.' Jangan mengarang. "
    "5. Jika relevan, sebutkan sumbernya dengan format: (file, halaman X). "
    "6. Jika ada konteks percakapan sebelumnya, gunakan itu untuk menjawab pertanyaan "
    "lanjutan dengan tepat. "
    "7. Jangan mengulang isi pertanyaan; langsung ke jawaban."
)


@dataclass
class Source:
    source: str
    page: int
    heading: str
    text: str
    distance: float


@dataclass
class RAGAnswer:
    answer: str
    sources: list[Source]
    model: str | None = None
    cached: bool = False


class RAGEngine:
    def __init__(
        self,
        store: VectorStore | None = None,
        llm: LLMClient | None = None,
        top_k: int = 5,
        cache: SemanticCache | None = None,
        use_cache: bool = True,
    ) -> None:
        self.store = store or VectorStore()
        self.llm = llm or LLMClient()
        self.top_k = top_k
        self.use_cache = use_cache
        self.cache = cache if cache is not None else SemanticCache(self.store)

    # ------------------------------------------------------------------
    # Prompt builder (dipakai query & stream_query)
    # ------------------------------------------------------------------
    def _build_messages(
        self,
        question: str,
        sources: list[Source],
        history: list[dict] | None = None,
        summary: str | None = None,
    ) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Ringkasan percakapan sebelumnya (pakai ini untuk mengingat "
                        "topik/fakta yang sudah dibahas):\n"
                        f"{summary}"
                    ),
                }
            )
        if history:
            messages.extend(
                {"role": m["role"], "content": m["content"]} for m in history
            )
        messages.append(
            {
                "role": "user",
                "content": f"KONTEKS:\n{self._build_context(sources)}\n\nPERTANYAAN:\n{question}",
            }
        )
        return messages

    def query(
        self,
        question: str,
        top_k: int | None = None,
        where: dict | None = None,
        history: list[dict] | None = None,
        summary: str | None = None,
    ) -> RAGAnswer:
        """Jawab pertanyaan berdasarkan dokumen terindeks (dengan cache).

        Args:
            question: Pertanyaan user.
            top_k: Jumlah chunk konteks.
            where: Filter dokumen untuk retrieval.
            history: Riwayat percakapan [{role, content}, ...]. Jika ada,
                disertakan ke prompt LLM dan cache dinonaktifkan (jawaban
                bergantung konteks percakapan).
            summary: Ringkasan percakapan sebelumnya (memori jangka panjang).
        """
        top_k = top_k or self.top_k
        has_history = bool(history)

        # 1. Cek cache (hanya untuk query tanpa riwayat — konteks statis)
        if self.use_cache and not has_history:
            entry = self.cache.get(question, where)
            if entry is not None:
                logger.info("Cache HIT untuk: %r (mirip: %r)", question, entry.matched_question)
                return RAGAnswer(
                    answer=entry.answer,
                    sources=self._retrieve_sources(question, top_k, where),
                    model=entry.model,
                    cached=True,
                )

        # 2. Miss: retrieve + LLM (dengan history bila ada)
        sources = self._retrieve_sources(question, top_k, where)
        if not sources:
            return RAGAnswer(
                answer="Tidak ada dokumen terindeks yang relevan.",
                sources=[],
            )

        messages = self._build_messages(question, sources, history, summary)
        response = self.llm.chat(messages, max_tokens=ANSWER_MAX_TOKENS)

        # 3. Simpan hasil ke cache (hanya query statis)
        if self.use_cache and not has_history:
            self.cache.put(question, response.text, response.model, where)

        return RAGAnswer(
            answer=response.text,
            sources=sources,
            model=response.model,
        )

    async def stream_query(
        self,
        question: str,
        top_k: int | None = None,
        where: dict | None = None,
        history: list[dict] | None = None,
        summary: str | None = None,
    ) -> AsyncIterator[dict]:
        """Versi streaming dari query(). Me-yield event dict:

        - {"type": "meta", "sources": [...], "cached": bool, "model": str|None}
          dikirim sebelum delta (supaya UI bisa render sumber lebih awal).
        - {"type": "delta", "text": str} untuk setiap potongan jawaban.
        - {"type": "done", "answer": str} sebagai penanda selesai.
        """
        top_k = top_k or self.top_k
        has_history = bool(history)

        # Cache: hanya untuk query statis (tanpa riwayat)
        if self.use_cache and not has_history:
            entry = self.cache.get(question, where)
            if entry is not None:
                logger.info("Cache HIT untuk: %r (mirip: %r)", question, entry.matched_question)
                sources = self._retrieve_sources(question, top_k, where)
                yield {
                    "type": "meta",
                    "sources": sources,
                    "cached": True,
                    "model": entry.model,
                }
                yield {"type": "delta", "text": entry.answer}
                yield {"type": "done", "answer": entry.answer}
                return

        sources = self._retrieve_sources(question, top_k, where)
        if not sources:
            msg = "Tidak ada dokumen terindeks yang relevan."
            yield {"type": "meta", "sources": [], "cached": False, "model": None}
            yield {"type": "delta", "text": msg}
            yield {"type": "done", "answer": msg}
            return

        messages = self._build_messages(question, sources, history, summary)
        # Kirim metadata (sumber, model) lebih dulu supaya UI bisa render awal
        yield {
            "type": "meta",
            "sources": sources,
            "cached": False,
            "model": self.llm.model,
        }

        parts: list[str] = []
        async for delta in self.llm.astream_chat(messages, max_tokens=ANSWER_MAX_TOKENS):
            parts.append(delta)
            yield {"type": "delta", "text": delta}

        answer = "".join(parts)
        if self.use_cache and not has_history:
            self.cache.put(question, answer, self.llm.model, where)

        yield {"type": "done", "answer": answer}

    # ------------------------------------------------------------------
    # Helper untuk multi-session chat
    # ------------------------------------------------------------------
    def generate_title(self, question: str) -> str:
        """Auto-judul singkat (max 5 kata) dari pertanyaan pertama."""
        prompt = (
            "Buat judul singkat (maksimal 5 kata) untuk percakapan yang dimulai "
            f"dengan pertanyaan ini. Hanya jawab judulnya saja, tanpa tanda kutip "
            f"atau titik:\n\nPertanyaan: {question}"
        )
        try:
            response = self.llm.chat(
                [{"role": "user", "content": prompt}], max_tokens=30
            )
            title = " ".join(response.text.strip().split()[:6])
            return title[:60] or "New Chat"
        except Exception as exc:  # fallback: jangan biarkan auto-title merusak query
            logger.warning("Auto-title gagal: %s", exc)
            return "New Chat"

    def summarize(self, messages: list[dict]) -> str:
        """Ringkas percakapan untuk memori jangka panjang (anti-pelupa)."""
        transcript = "\n".join(
            f"{m['role']}: {m['content'][:500]}" for m in messages
        )
        prompt = (
            "Buat ringkasan percakapan ini dalam bahasa Indonesia. Ringkasan akan "
            "dipakai sebagai memori jangka panjang asisten supaya tidak lupa konteks "
            "di percakapan lanjutan. WAJIB pertahankan: topik utama, fakta teknis, "
            "istilah, preferensi pengguna, dokumen yang dibahas, dan hal yang belum "
            "tuntas. Maksimal 200 kata, tanpa basa-basi:\n\n"
            f"{transcript}"
        )
        try:
            response = self.llm.chat(
                [{"role": "user", "content": prompt}], max_tokens=300
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning("Auto-summary gagal: %s", exc)
            return ""

    def _retrieve_sources(
        self, question: str, top_k: int, where: dict | None
    ) -> list[Source]:
        """Ambil chunk paling relevan beserta metadata sumbernya."""
        results = self.store.search(question, top_k=top_k, where=where)
        return [
            Source(
                source=r["metadata"]["source"],
                page=r["metadata"]["page"],
                heading=r["metadata"]["heading"],
                text=r["text"],
                distance=r["distance"],
            )
            for r in results
        ]

    @staticmethod
    def _build_context(sources: list[Source]) -> str:
        """Susun konteks ber-nomor agar LLM bisa merujuk ke sumber."""
        blocks = []
        for i, src in enumerate(sources, 1):
            blocks.append(
                f"[{i}] (file: {src.source}, halaman: {src.page}, bagian: {src.heading})\n{src.text}"
            )
        return "\n\n".join(blocks)
