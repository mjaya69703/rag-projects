"""Test fitur #10: parse_markdown — heading, chunk index, metadata, panjang.

Jalankan: python tests/test_ingest_md.py  atau  pytest tests/test_ingest_md.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.md_parser import NO_HEADING_LABEL, parse_markdown

# Sampel: paragraf intro sebelum heading pertama (harus jadi "Intro"),
# section panjang > 500 char (harus dipecah), heading dengan trailing #,
# dan fence kode berisi "#" yang TIDAK boleh jadi heading.
SAMPLE = """\
Catatan awal tanpa heading. Konteks pembuka sebelum judul utama dokumen,
satu paragraf biasa yang tidak memakai tanda pagar sama sekali.

# Panduan Jaringan Komputer

Pengantar jaringan: kumpulan perangkat yang saling terhubung untuk berbagi
data dan sumber daya. Jaringan memungkinkan pertukaran informasi secara
cepat tanpa terbatas lokasi fisik.

## VLAN

VLAN adalah metode mempartisi satu jaringan fisik menjadi beberapa jaringan
logis. Dengan VLAN, broadcast domain diperkecil sehingga lalu lintas
jaringan lebih efisien. Setiap VLAN memiliki identitas nomor antara 1
hingga 4094, dan komunikasi antar VLAN memerlukan perangkat layer 3.

### Konfigurasi VLAN ##

Konfigurasi VLAN biasanya dilakukan pada port switch dengan mode access
atau trunk. Port access melewatkan trafik satu VLAN saja, sedangkan port
trunk melewatkan banyak VLAN menggunakan tag 802.1Q. Mode trunk dipakai
ketika menghubungkan switch ke switch lain atau ke router.

## Routing

Routing adalah proses memilih jalur terbaik untuk mengirim paket data dari
sumber ke tujuan. Router membaca tabel routing untuk menentukan ke mana
paket diteruskan. Tabel routing dapat diisi statis oleh administrator atau
dinamis melalui protokol routing seperti OSPF dan BGP. Metrik seperti hop
count, bandwidth, dan delay dipakai untuk membandingkan beberapa jalur
yang tersedia. Administrasi routing yang buruk menyebabkan paket terbuang
dan koneksi lambat, sehingga pemantauan berkala terhadap tabel routing
sangat penting untuk menjaga performa jaringan tetap optimal. Selain itu,
dokumentasi topologi dan kebijakan routing perlu diperbarui setiap kali
ada perubahan infrastruktur agar tim operasional tidak salah mengambil
keputusan saat terjadi gangguan. Dengan perencanaan yang matang, masalah
routing dapat dicegah sejak awal sebelum berdampak ke pengguna akhir.

```
# ini kode, bukan heading markdown
def contoh():
    return True
```
"""


def _sample(tmp_path: Path) -> Path:
    path = tmp_path / "catatan.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_headings_detected(tmp_path: Path) -> None:
    chunks = parse_markdown(_sample(tmp_path))
    headings = {c.metadata["heading"] for c in chunks}
    assert "Panduan Jaringan Komputer" in headings
    assert "VLAN" in headings
    assert "Konfigurasi VLAN" in headings  # trailing "##" harus dibersihkan
    assert "Routing" in headings
    # "# ini kode" di dalam fence TIDAK boleh jadi heading
    assert "ini kode, bukan heading markdown" not in headings


def test_intro_before_first_heading(tmp_path: Path) -> None:
    chunks = parse_markdown(_sample(tmp_path))
    intro = [c for c in chunks if c.metadata["heading"] == NO_HEADING_LABEL]
    assert intro, "teks sebelum heading pertama harus ber-heading 'Intro'"
    assert "Catatan awal tanpa heading" in intro[0].text


def test_chunk_index_sequential_and_metadata(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    chunks = parse_markdown(path)
    assert chunks, "parse_markdown() tidak menghasilkan chunk"
    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        assert meta["source"] == path.name, f"source salah: {meta}"
        assert meta["chunk_index"] == i, "chunk_index harus berurutan global"
        assert meta["page"] == 1, "page harus 1 untuk markdown"
        assert meta["heading"], f"heading kosong di chunk {i}"
        assert set(meta) == {"source", "page", "heading", "chunk_index"}


def test_long_section_split_into_multiple_chunks(tmp_path: Path) -> None:
    chunks = parse_markdown(_sample(tmp_path))
    routing = [c for c in chunks if c.metadata["heading"] == "Routing"]
    assert len(routing) >= 2, "section panjang harus dipecah jadi beberapa chunk"
    assert all(c.metadata["heading"] == "Routing" for c in routing)


def test_chunk_length_within_limit(tmp_path: Path) -> None:
    chunks = parse_markdown(_sample(tmp_path))
    for chunk in chunks:
        assert len(chunk.text) <= 550, (
            f"chunk terlalu panjang: {len(chunk.text)} chars"
        )
        assert chunk.text.strip(), "chunk tidak boleh kosong"


def test_source_override_and_missing_file(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    chunks = parse_markdown(path, source="nama-kustom.md")
    assert all(c.metadata["source"] == "nama-kustom.md" for c in chunks)

    try:
        parse_markdown(tmp_path / "tidak-ada.md")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("file yang tidak ada harus memicu FileNotFoundError")


def test_txt_file_supported(tmp_path: Path) -> None:
    path = tmp_path / "catatan.txt"
    path.write_text("# Judul Teks\n\nIsi file teks biasa.", encoding="utf-8")
    chunks = parse_markdown(path)
    assert chunks
    assert chunks[0].metadata["heading"] == "Judul Teks"
    assert chunks[0].metadata["source"] == "catatan.txt"
