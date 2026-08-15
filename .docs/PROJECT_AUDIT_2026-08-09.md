# Audit Proyek Personal AI Knowledge Base

Tanggal audit: 2026-08-09  
Scope: arsitektur, keamanan, reliabilitas, retrieval/RAG, fitur belajar, UX, operasional, dokumentasi, dan nilai guna untuk user.  
Sumber: codebase aktual, `graphify-out/`, `.agents/00-08`, `docs/`, serta test/build yang dapat dijalankan.

## Ringkasan eksekutif

Proyek ini sudah menjadi prototype RAG yang cukup lengkap: ingestion multi-format, hybrid retrieval, session chat, streaming, citation, dan learning loop sudah tersambung. Fondasi modularnya juga cukup sehat; graphify mendeteksi 869 node, 1.919 edge, tidak ada import cycle, dan test parser/database/ingestion yang dijalankan di workspace menghasilkan 47 pass.

Tetapi status “selesai 100%” belum layak dipakai sebagai status produksi. Hambatan utama bukan jumlah fitur, melainkan trust boundary dan reliability:

1. Ingest URL membuka risiko SSRF karena hanya memvalidasi skema/host, lalu mengikuti redirect dan memiliki fallback `curl`.
2. API tidak memiliki autentikasi aplikasi. Cloudflare Access masih prosedur deployment manual, sehingga akses langsung ke port atau salah konfigurasi tunnel membuka upload, delete, query, metrics, dan data chat.
3. Ingestion dan embedding berlangsung sinkron di request; 50 MB dibaca ke RAM sekaligus. Ini berisiko timeout, OOM, dan UI yang terlihat “loading” tetapi tidak dapat dibatalkan secara nyata.
4. Kualitas learning analytics masih berupa sinyal kasar: `wrong` pada weak spot selalu 0, quiz mengambil satu chunk per heading secara langsung, dan spaced repetition bukan algoritme yang cukup kaya untuk dipercaya sebagai tutor.
5. Ada drift dokumentasi besar: `docs/` masih menyebut Streamlit, GPTCache, LangChain splitter, dan stack versi lama, sementara aplikasi aktual adalah React/Vite/Bun dengan cache ChromaDB custom.

Penilaian saat ini: **prototype kuat / production readiness rendah-menengah**. Prioritas berikutnya sebaiknya mengurangi risiko dan meningkatkan trust, bukan menambah fitur baru.

## Temuan berdasarkan prioritas

### P0 — harus dibereskan sebelum remote/public use

#### P0-01 — SSRF pada ingest URL

- Evidence: `app/url_parser.py:262-266` hanya memastikan `http/https` dan `netloc`; `app/url_parser.py:136-142` mengikuti redirect; `app/url_parser.py:153-161` mengirim URL ke `curl`.
- Dampak: service dapat dipakai untuk meminta alamat private/internal seperti loopback, RFC1918, metadata service, atau host internal setelah redirect. Karena endpoint ini juga belum memiliki auth aplikasi, risikonya bukan sekadar misuse oleh user tepercaya.
- Seharusnya: resolve DNS lalu blok private, loopback, link-local, multicast, reserved, dan metadata IP; validasi setiap redirect; batasi port ke 80/443; gunakan egress proxy/allowlist bila memungkinkan; jangan fallback ke `curl` tanpa menerapkan policy yang sama; batasi ukuran response dan content type.
- Acceptance: test untuk `127.0.0.1`, `10.0.0.0/8`, `169.254.169.254`, IPv6 local/link-local, redirect public→private, dan response oversized.

#### P0-02 — Tidak ada autentikasi/otorisasi di application boundary

- Evidence: `deploy/README-DEPLOY.md:19-22,68-84` menyatakan Cloudflare Access adalah satu-satunya gerbang; `app/main.py:308-316` mengekspos health/metrics; endpoint operasi di `app/main.py:339-425,753-861,912-1000` tidak memeriksa identitas atau role.
- Dampak: jika port 8000 dapat dijangkau langsung, jika tunnel salah route, atau jika service dipakai di jaringan internal yang tidak sepenuhnya dipercaya, siapa pun dapat membaca metadata, mengunggah, menghapus indeks, mengubah kategori, menambah anotasi, dan mengakses riwayat sesi.
- Seharusnya: tambahkan auth middleware/token atau verifikasi signed identity header dari Cloudflare Access dengan fail-closed behavior; pisahkan endpoint public health dari endpoint data; audit log actor/action; jangan menganggap deployment config sebagai satu-satunya kontrol keamanan.
- Acceptance: request tanpa kredensial ke seluruh endpoint mutasi/data mendapat 401/403; `/health` tetap dapat dipakai systemd; identity yang valid tercatat di audit log.

#### P0-03 — Dokumen pribadi dikirim ke LLM eksternal tanpa kontrol privasi yang terlihat

- Evidence: `docs/01_TECH_STACK.md` mengatur endpoint LLM eksternal; `app/rag_engine.py:112-116,175-180` memasukkan isi chunk ke prompt dan menyimpan jawaban ke semantic cache; tidak ada consent, retention policy, redaction, atau UI disclosure yang terdokumentasi.
- Dampak: user dapat mengira “local knowledge base” berarti data tetap lokal, padahal isi dokumen dan konteks chat keluar ke provider LLM. Cache dan SQLite juga menyimpan materi/jawaban tanpa lifecycle penghapusan yang setara.
- Seharusnya: tampilkan disclosure yang jelas saat konfigurasi pertama, sediakan mode local/private atau provider yang dapat dipilih, redaction untuk secret/PII, retention/clear-all untuk cache/chat, dan dokumentasikan data flow serta trust boundary.

### P1 — risiko tinggi untuk kualitas dan reliabilitas

#### P1-01 — Ingestion sinkron dan tidak atomic

- Evidence: `app/main.py:355-384` membaca seluruh upload ke memory, menulis file, parsing, menghapus index lama, lalu menambah index baru dalam satu request.
- Dampak: upload besar memblokir worker; kegagalan setelah delete dapat meninggalkan dokumen lama hilang dan index baru setengah jadi; file invalid dapat tertinggal di `uploads/`; tidak ada job id/progress/resume/cancel.
- Seharusnya: gunakan job queue/background worker, staging directory, checksum/versioned document record, temp collection lalu swap atomically, cleanup saat gagal, dan status ingestion yang bisa dipantau frontend.

#### P1-02 — Lifecycle file, index, dan metadata tidak konsisten

- Evidence: upload disimpan di `settings.upload_dir / filename` (`app/main.py:363-364`), tetapi source index dapat diganti (`app/main.py:366`); delete hanya menghapus vector dan menulis deleted marker (`app/main.py:851-861`), tidak menghapus file atau mapping kategori.
- Dampak: disk terus membesar, file dengan source custom sulit dilacak, re-upload/watch-folder dapat berperilaku tidak terduga, dan user melihat “dihapus” padahal salinan fisik masih ada.
- Seharusnya: buat document registry sebagai source of truth yang menyimpan file path, checksum, source type, status, error, created/updated; definisikan delete sebagai archive atau purge dengan pilihan eksplisit; hapus mapping kategori/cache terkait saat purge.

#### P1-03 — Prompt injection dari isi dokumen belum dimitigasi

- Evidence: `app/rag_engine.py:96-116,327-333` menaruh teks dokumen langsung di pesan user sebagai `KONTEKS`; system prompt meminta grounding, tetapi tidak ada delimiter/aturan eksplisit bahwa instruksi di dalam dokumen adalah data.
- Dampak: dokumen yang berisi “abaikan instruksi sebelumnya”, prompt palsu, atau data manipulatif dapat memengaruhi jawaban, terutama karena output LLM kemudian dirender dan disimpan.
- Seharusnya: tandai context sebagai untrusted quoted data, instruksikan model untuk mengabaikan perintah dari context, gunakan citation berbasis chunk id, validasi bahwa klaim/sumber berasal dari retrieved chunks, dan tampilkan status “grounded/uncertain”.

#### P1-04 — Relevance floor bukan evaluasi groundedness yang cukup

- Evidence: `app/rag_engine.py:162-173` memutuskan berdasarkan distance minimum; hybrid RRF dapat membawa chunk jauh ke atas, sebagaimana komentar kode sendiri mengakui.
- Dampak: jawaban bisa lolos hanya karena satu chunk paling dekat tetapi tidak benar-benar menjawab; sebaliknya pertanyaan follow-up tidak dievaluasi dengan cara yang sama. Citation berarti “retrieved”, bukan bukti bahwa jawaban didukung.
- Seharusnya: evaluasi relevance per chunk, reranker/cross-encoder opsional, threshold terkalibrasi per model/corpus, citation entailment atau claim check, dan dataset evaluasi nyata Indonesia/Inggris.

#### P1-05 — Streaming dan synchronous endpoint menduplikasi logika query

- Evidence: `app/main.py:430-515` dan `app/main.py:518-640` mengulang pembangunan filter/history/grounding/session persistence; graphify juga menunjukkan `main.py` sebagai hub besar dan `VectorStore`/`RAGEngine` sebagai god nodes.
- Dampak: bug parity mudah terjadi antara `/query` dan `/query/stream`; perubahan policy harus dilakukan dua kali. Ini meningkatkan coupling dan biaya pemeliharaan.
- Seharusnya: ekstrak `QueryContext`, service use-case, dan satu pipeline persistence; endpoint hanya mengadaptasi hasil ke JSON atau SSE.

#### P1-06 — State runtime global tidak cocok untuk scale-out/restart

- Evidence: rate limit memakai `_RATE_LIMIT` in-memory (`app/main.py:246-258`), metrics memakai `app.state.metrics` (`app/main.py:91-96,313-316`), Chroma/SQLite embedded dipakai oleh satu service.
- Dampak: rate limit dan metrics reset saat restart, tidak konsisten jika worker >1, dan concurrent ingestion/query dapat berhadapan dengan lock/file contention.
- Seharusnya: tetapkan single-process sebagai constraint eksplisit atau pindahkan rate limit/metrics/job state ke backend bersama; tambahkan lock dan concurrency policy untuk mutasi index.

#### P1-07 — URL ingestion hanya mengambil HTML statis dan tanpa batas response

- Evidence: `app/url_parser.py:136-150,224-259` menerima bytes response lalu decode/chunk; tidak ada pembatasan content length, content type, robots/terms policy, atau deteksi halaman JS-only.
- Dampak: penggunaan memory dan kualitas index tidak terprediksi; halaman modern dapat terindeks sebagai boilerplate kosong, sedangkan file non-HTML besar bisa diterima sebelum magic-byte handling.
- Seharusnya: cek headers dan ukuran sebelum membaca penuh, dukung content type yang jelas, beri status “partial/unsupported”, dan sediakan preview sebelum index.

### P2 — masalah fitur dan kegunaan yang membuat produk terasa belum matang

#### P2-01 — Command palette yang ditampilkan di sidebar tidak terhubung

- Evidence: `frontend/src/components/Sidebar.tsx:70-74` memiliki button `Perintah` tanpa `onClick`; command dialog sebenarnya hanya dibuka oleh global key handler di `frontend/src/pages/Chat.tsx:153-162`.
- Dampak: user mengklik affordance yang tampak interaktif tetapi tidak melakukan apa-apa. Di halaman selain Chat, shortcut juga tidak dipasang oleh `Chat.tsx`.
- Seharusnya: pindahkan command-palette state/provider ke layout global atau hilangkan tombol dari sidebar; pastikan klik dan Ctrl/Cmd+K bekerja di semua route.

#### P2-02 — Status “API terhubung” di sidebar statis

- Evidence: `frontend/src/components/Sidebar.tsx:75-78` selalu merender `API terhubung`; health check nyata hanya di Settings.
- Dampak: UI dapat memberi rasa aman ketika backend sudah mati atau request gagal.
- Seharusnya: gunakan context health state, tampilkan connecting/degraded/offline, retry, dan timestamp pemeriksaan terakhir.

#### P2-03 — Learning loop mengukur perilaku, bukan penguasaan materi

- Evidence: `app/learning.py:154-160` menyatakan `wrong` selalu 0; `app/learning.py:255-280` memilih chunk langsung dari collection; `app/learning.py:105-124` hanya menggandakan interval atau reset ke 1 hari.
- Dampak: weak spot lebih tepat disebut “sering ditanya”, bukan topik yang terbukti lemah; quiz dapat bias ke urutan collection; spaced repetition tidak mempertimbangkan confidence, difficulty, response time, atau forgetting curve.
- Seharusnya: simpan hasil per soal/topik, kaitkan pertanyaan dengan chunk/source, gunakan scheduler yang terdokumentasi (misalnya FSRS/SM-2 yang benar), dan bedakan metrik exposure, correctness, dan mastery.

#### P2-04 — Quiz grading masih mempercayai sebagian output LLM

- Evidence: `app/learning.py:362-388` mengambil `score` dan `total` dari output LLM, meskipun correctness detail dihitung terhadap answer key; backend hanya memvalidasi bentuk dasar request (`app/main.py:174-176`).
- Dampak: skor agregat dapat tidak cocok dengan detail; client dapat mengirim questions/answers yang bukan paket soal yang diterbitkan server.
- Seharusnya: simpan quiz attempt server-side dengan id dan answer key, hitung skor deterministik, gunakan LLM hanya untuk explanation, dan validasi jumlah/indeks opsi.

#### P2-05 — Tidak ada observability produksi yang memadai

- Evidence: `/metrics` hanya mengembalikan counter in-memory (`app/main.py:313-316`); test/performance checklist di `docs/07_TESTING_AND_QA.md` masih banyak unchecked; belum ada latency histogram, ingestion failure, queue depth, model load time, disk usage, atau alert.
- Dampak: user/operator tidak tahu apakah lambat karena embedding, Chroma, LLM, atau jaringan; batas RAM dan target <5 detik belum terbukti.
- Seharusnya: structured metrics terpersisten/Prometheus-compatible, correlation id sampai LLM call, error taxonomy, disk/RAM health, dan smoke test deployment nyata.

#### P2-06 — Test coverage kuat untuk unit path, lemah untuk acceptance path

- Evidence: `tests/test_frontend.py:22-47` hanya memeriksa HTML shell/assets; `docs/07_TESTING_AND_QA.md` mengakui latency, RAM, security, dan sebagian LLM test belum dilakukan.
- Verifikasi audit: 47 test parser/database/ingestion pass dengan `--basetemp .pytest-tmp`; test API gagal di environment ini saat model Hugging Face mencoba network; `bun run build` gagal karena `EPERM` membuka `frontend/node_modules/picomatch/index.js`.
- Seharusnya: tambah browser E2E (upload→query→citation→delete, session, learning), fixture embedding offline, performance benchmark CI, security tests SSRF/auth, dan build environment reproducible.

#### P2-07 — Dokumentasi kontradiktif dan berisiko menyesatkan

- Evidence: `docs/02_GOALS_AND_SCOPE.md` dan `docs/03_TECHNICAL_SPECIFICATION.md` masih menyebut Streamlit, GPTCache, LangChain 0.1, ChromaDB lama, dan PDF-only; `.agents/00-08` menyebut React 19/Bun dan cache custom.
- Dampak: agent/developer berikutnya bisa mengikuti arsitektur yang sudah tidak ada, salah mengubah dependency, atau mengira deployment dan security telah selesai.
- Seharusnya: tetapkan satu canonical docs set, tandai dokumen historis, update diagram workflow, dependency versions, API contract, data retention, dan status “implemented/verified/not verified”.

#### P2-08 — Backup, migration, dan recovery belum menjadi fitur operasional

- Evidence: state penting berada di `data/chroma_db`, `data/chat.db`, dan `uploads/`; deployment hanya membuat direktori/systemd (`deploy/install_lxc.sh:122-133`), tidak ada backup/restore/checksum/migration version.
- Dampak: disk corruption, OOM kill, salah hapus, atau upgrade model dapat menghilangkan knowledge base dan riwayat belajar.
- Seharusnya: command backup/restore terverifikasi, backup SQLite + uploads + index metadata, retention policy, migration/version manifest, dan prosedur re-index yang terdokumentasi.

## Catatan arsitektur dari graphify

- Graphify dibangun dari commit yang sama dengan HEAD: `0ea273b04561d9e70d1ef5f3d4b31ee01e25fd07`, sehingga dapat dipakai sebagai peta aktual untuk audit ini.
- `VectorStore` (65 edge), `RAGEngine` (50), `parse_pdf` (29), `_conn` (26), dan `main.py` (23) adalah hub utama. Ini bukan otomatis bug, tetapi menunjukkan area yang paling mahal bila berubah dan kandidat utama untuk pemecahan boundary.
- Tidak ada import cycle yang terdeteksi.
- Graphify menandai 69 isolated nodes dan 78 inferred edges. Relasi inferred tidak saya jadikan bukti tunggal; saya gunakan hanya sebagai navigasi lalu cek kembali ke source.

## Urutan perbaikan yang disarankan

### Gelombang 1 — secure the product

1. SSRF-safe URL fetcher dengan redirect/IP/content-size policy.
2. Application auth/identity verification dan audit log.
3. Privacy disclosure, retention, purge, serta opsi provider/local mode.
4. Security tests dan direct-port smoke test.

### Gelombang 2 — make ingestion trustworthy

1. Document registry + checksum/version/status.
2. Async job ingestion dengan staging dan atomic swap.
3. Disk/RAM/latency observability.
4. Backup/restore dan re-index command.

### Gelombang 3 — make learning genuinely useful

1. Server-side quiz attempts dan deterministic scoring.
2. Mapping hasil ke source/chunk/topic.
3. Scheduler spaced repetition yang terdokumentasi.
4. E2E flow dan UX untuk “next review”, bukan hanya dashboard angka.

### Gelombang 4 — documentation and polish

1. Satukan `docs/` dan `.agents/` menjadi satu status canonical.
2. Hubungkan command palette dan health status global.
3. Jalankan browser verification pada 320/375/414/768 px dan alur user nyata.

## Kesimpulan nilai guna

Untuk pemilik proyek yang ingin belajar RAG dan meng-query koleksi pribadi secara lokal, proyek ini sudah sangat membantu sebagai lab/prototype. Untuk user yang mempercayakan dokumen sensitif dan mengharapkan tutor belajar yang akurat, saat ini belum cukup: trust boundary belum aman, recovery belum ada, dan analytics belajar belum merepresentasikan mastery secara kuat. Ukuran keberhasilan berikutnya sebaiknya bukan “berapa banyak fitur tampil”, melainkan “bisakah user memasukkan dokumen, mendapatkan jawaban yang dapat diverifikasi, memahami data yang keluar, memulihkan sistem saat gagal, dan belajar dari hasil yang benar-benar terukur.”

## Batas verifikasi audit

- Graphify: terverifikasi fresh terhadap HEAD.
- Parser/database/ingestion subset: 47 pass dengan temp base di workspace.
- API suite: belum dapat dinyatakan pass; gagal saat model embedding mencoba akses Hugging Face dari environment audit.
- Frontend build: belum dapat dinyatakan pass; Bun/Vite mendapat `EPERM` saat membuka `frontend/node_modules/picomatch/index.js`.
- Penilaian visual browser: belum dilakukan karena audit ini tidak menjalankan browser; temuan UX di atas berasal dari implementasi dan acceptance path code-level.
