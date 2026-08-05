# 06 — Lessons Learned (BACA SEBELUM MENGUBAH APA PUN)

Daftar pelajaran berbayar dari proses pengembangan. Melanggar = mengulang kesalahan.

## 1. GPTCache tidak bisa dipakai (Sprint 3)
GPTCache 0.1.44 rusak di stack ini:
- Auto-install `faiss-cpu` saat runtime klaim sukses padahal gagal.
- Memakai API ChromaDB lama yang sudah deprecated di chromadb 1.5.9.
- `get_data_manager(data_path=...)` tanpa CacheBase/VectorBase eksplisit = cache
  **in-memory** (hilang saat restart), melanggar requirement persistent.

**Solusi:** semantic cache ditulis sendiri (`app/semantic_cache.py`) di atas
ChromaDB collection `query_cache`. Jangan coba "perbaiki" dengan GPTCache lagi.

## 2. e5-small gagal di retrieval bahasa informal (Sprint 3, sudah di-revert)
Benchmark awal menguji **query-vs-query** (parafrase & cache hit rate) — e5 menang
(hit rate 73%→100%, parafrase "vlan itu apa?" 0.59→0.02). Tapi **retrieval
query-vs-dokumen** untuk bahasa gaul ("produk apa yang ditawarin sama mereka")
gagal total: nyasar ke chunk footer/routing, jawaban jadi "tidak ditemukan".

**Keputusan: tetap MiniLM.** MiniLM (paraphrase model) lebih tolerant bahasa
sehari-hari. **Pelajaran: benchmark model embedding WAJIB menguji retrieval nyata
(query-vs-dokumen), bukan cuma parafrase query-vs-query.**

## 3. Ganti model embedding = wajib reset & re-index + clear cache
Vektor model lama tidak kompatibel dengan model baru. Prosedur:
```cmd
.venv\Scripts\python -c "from app.vector_store import VectorStore; from app.semantic_cache import SemanticCache; s=VectorStore(); s.reset(); SemanticCache(s).clear(); s.close()"
.venv\Scripts\python ingest.py uploads\<file> --source "X" --replace
```

## 4. Slide deck (PDF presentasi) butuh perlakuan khusus
- Segmen pendek (<120 char) di-merge ke segmen sebelumnya (`_merge_short_segments`)
  supaya tidak jadi chunk serpihan.
- Footer template (`Huawei Proprietary...`) dan baris angka (nomor halaman)
  di-skip. Dampak nyata: chunk Huawei 177→147, noise "Intro" 15→1.
- Heading noise (`Intro`, `Root`, `Owner`) masih mungkin muncul — biasanya label
  slide; kalau mengganggu pertimbangkan deteksi slide-mode (chunk per halaman).

## 5. Cache threshold 0.25 (MiniLM)
Measured: "jelaskan apa itu VLAN" vs "Apa itu VLAN?" ≈ 0.03 (HIT), pertanyaan beda
makna >0.5 (MISS). "vlan itu apa?" (urutan kata beda) ≈ 0.59 → **tidak** ketangkap
cache MiniLM — itu keterbatasan model, bukan bug. e5 bisa menangkapnya tapi bikin
retrieval rusak (lihat #2). Trade-off sudah diterima.

## 6. Top-K untuk pertanyaan luas
Default 5 cukup untuk pertanyaan spesifik. Pertanyaan "isinya apa?", "bikin soal
PG" butuh `-k 10/15`. Opsi masa depan: auto top-k via threshold similarity.

## 7. Auto-title dan summary memakai LLM (token ekstra)
`generate_title` (max_tokens 30) & `summarize` (max_tokens 256) dipanggil per
session. Sudah di-optimasi minimal, tapi tetap konsumsi token API — jangan
dipanggil berlebihan.

## 8. max_tokens jawaban (berubah 02-08-2026)
Dulu 1024 → latency >5 detik; turun ke 512 → 3.7 detik. **Sekarang naik lagi ke
1024 (env `RAG_MAX_TOKENS`)** karena jawaban streaming via SSE — persepsi latency
hilang walau waktu total sama. User minta jawaban tidak terlalu singkat; prompt
sistem juga diubah (larangan "maks 3-5 kalimat" dihapus).

## 9. Test Python 3.14
Semua dependency versi terbaru jalan di cp314. Jangan downgrade ke versi lama spec
— tidak ada wheel.

## 10. Semantic cache WAJIB aware filter dokumen (06-08-2026)
Sebelumnya `SemanticCache.get(question, where)` mengabaikan `where` saat mencari
kemiripan — pertanyaan yang sama bisa HIT dari cache milik filter dokumen lain,
jawaban jadi bocor lintas-dokumen (mis. jawaban dari dokumen X dipakai saat filter
dokumen Y). Fix: simpan bentuk kanonik `where` di metadata entry, lalu tolak entry
yang filter-nya berbeda (MISS). Entri lama tanpa metadata `where` otomatis MISS
sekali lalu diganti — konservatif dan aman.

**Catatan testing:** pertanyaan IDENTIK dengan filter berbeda menghasilkan embedding
identik → distance 0.0 → tie di hnswlib, pemenangnya tidak deterministik antar
build. Test isolasi filter memakai parafrase dalam-threshold (bukan string identik)
supaya nearest-neighbor tidak ambigu.

## 11. Output LLM/dokumen = data tidak tepercaya (06-08-2026)
Markdown jawaban LLM dirender via `innerHTML` tanpa sanitasi → XSS (jawaban bisa
memuat `<script>` dari isi dokumen/LLM). Fix: DOMPurify wajib sebelum `innerHTML`
untuk semua konten dari LLM/dokumen. Konten user (role=user) tetap `textContent`.
