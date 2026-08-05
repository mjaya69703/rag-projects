"""Generate PDF sampel berbahasa Indonesia untuk testing ingestion.

PDF dibuat dengan PyMuPDF, berisi struktur heading yang jelas
(judul > heading bab > sub-heading > body text) supaya smart chunking
berbasis heading bisa diuji.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

PAGE_W = 595.0  # A4
PAGE_H = 842.0
MARGIN = 60.0
BODY_SIZE = 11
HEADING_SIZE = 16
TITLE_SIZE = 22

BODY = (
    "Jaringan komputer adalah kumpulan perangkat yang saling terhubung untuk "
    "berbagi data dan sumber daya. Setiap perangkat dalam jaringan disebut "
    "node, dan koneksi antar node dapat berupa kabel atau nirkabel. "
    "Jaringan memungkinkan pengguna bertukar informasi secara cepat tanpa "
    "terbatas lokasi fisik. Teknologi ini menjadi fondasi dari internet "
    "yang kita gunakan sehari-hari. Protokol merupakan aturan yang mengatur "
    "cara komunikasi antar perangkat dalam jaringan. Tanpa protokol, "
    "perangkat dari vendor berbeda tidak akan mampu saling memahami data "
    "yang dikirim. Salah satu protokol paling penting adalah TCP/IP yang "
    "menjadi standar komunikasi data di seluruh dunia. Setiap paket data "
    "yang dikirim melalui jaringan akan dipecah menjadi bagian kecil, "
    "diberi alamat tujuan, lalu disusun kembali di sisi penerima. "
    "Keandalan pengiriman data sangat bergantung pada kualitas infrastruktur "
    "jaringan yang digunakan. Oleh karena itu, perencanaan jaringan yang "
    "baik mutlak diperlukan sebelum membangun infrastruktur baru. "
    "Administrator jaringan juga harus memahami konsep subnetting, "
    "routing, dan keamanan dasar agar jaringan berjalan stabil."
)

VLAN_BODY = (
    "Virtual Local Area Network atau VLAN adalah metode mempartisi satu "
    "jaringan fisik menjadi beberapa jaringan logis yang terpisah. "
    "Dengan VLAN, broadcast domain dapat diperkecil sehingga lalu lintas "
    "jaringan menjadi lebih efisien. Setiap VLAN memiliki identitas berupa "
    "nomor antara 1 hingga 4094. Perangkat dalam VLAN yang sama dapat "
    "berkomunikasi seolah-olah berada dalam satu switch fisik, meskipun "
    "secara fisik tersebar di beberapa switch. Komunikasi antar VLAN "
    "memerlukan perangkat layer 3 seperti router atau switch layer 3. "
    "Konfigurasi VLAN biasanya dilakukan pada port switch dengan mode "
    "access atau trunk. Port access hanya melewatkan trafik satu VLAN, "
    "sedangkan port trunk melewatkan trafik banyak VLAN menggunakan tag "
    "802.1Q. Manfaat utama VLAN antara lain peningkatan keamanan, "
    "pengurangan broadcast, dan fleksibilitas manajemen jaringan. "
    "Keamanan meningkat karena pengguna di VLAN berbeda tidak dapat "
    "mengakses langsung sumber daya di VLAN lain tanpa izin routing. "
    "Penerapan VLAN sangat umum di lingkungan perkantoran dan kampus. "
    "Misalnya, departemen keuangan, HRD, dan IT masing-masing diberi "
    "VLAN terpisah. Dengan demikian, gangguan pada satu departemen "
    "tidak memengaruhi departemen lainnya. Pemahaman tentang VLAN menjadi "
    "syarat wajib bagi calon administrator jaringan profesional. "
    "Sertifikasi jaringan seperti CCNA juga memasukkan materi VLAN "
    "sebagai bagian dari ujian inti. Oleh karena itu, praktik langsung "
    "mengkonfigurasi VLAN di switch sangat disarankan bagi mahasiswa "
    "yang ingin mendalami bidang jaringan komputer."
)

ROUTING_BODY = (
    "Routing adalah proses memilih jalur terbaik untuk mengirim paket "
    "data dari sumber ke tujuan. Perangkat yang bertanggung jawab atas "
    "proses ini disebut router. Router membaca tabel routing untuk "
    "menentukan ke mana paket harus diteruskan. Tabel routing dapat "
    "diisi secara statis oleh administrator atau secara dinamis melalui "
    "protokol routing. Protokol routing dinamis seperti OSPF dan BGP "
    "memungkinkan jaringan menyesuaikan diri secara otomatis ketika "
    "terjadi perubahan topologi. OSPF banyak digunakan pada jaringan "
    "internal perusahaan karena konvergensinya cepat. BGP digunakan "
    "antar penyedia layanan internet untuk bertukar informasi routing "
    "dalam skala global. Metrik routing seperti hop count, bandwidth, "
    "dan delay digunakan untuk membandingkan beberapa jalur yang "
    "tersedia. Administrasi routing yang buruk dapat menyebabkan "
    "paket terbuang dan koneksi menjadi lambat. Pemantauan berkala "
    "terhadap tabel routing dan kualitas jalur sangat penting untuk "
    "menjaga performa jaringan tetap optimal."
)

TROUBLESHOOTING_BODY = (
    "Troubleshooting jaringan adalah proses sistematis untuk menemukan "
    "dan memperbaiki masalah konektivitas. Langkah pertama biasanya "
    "memeriksa kabel dan indikator lampu pada perangkat. Setelah itu, "
    "administrator dapat menggunakan perintah ping untuk menguji "
    "konektivitas dasar antar perangkat. Jika ping gagal, perlu "
    "diperiksa konfigurasi IP, gateway, dan DNS. Tools seperti "
    "traceroute membantu melihat jalur yang dilalui paket dan "
    "menemukan titik kegagalan. Pencatatan log yang baik sangat "
    "membantu proses identifikasi masalah. Dokumentasi setiap "
    "perubahan konfigurasi juga mencegah munculnya masalah baru "
    "di kemudian hari."
)


def make_sample_pdf(path: str | Path) -> Path:
    """Buat PDF sampel bertema jaringan komputer di lokasi ``path``."""
    path = Path(path)
    doc = fitz.open()

    _add_block(doc, "Materi Jaringan Komputer", TITLE_SIZE)
    _add_block(doc, "Modul pembelajaran dasar jaringan untuk mahasiswa STI.", BODY_SIZE)
    _add_block(doc, "Bab 1: Pendahuluan", HEADING_SIZE)
    _add_block(doc, "1.1 Definisi Jaringan", HEADING_SIZE)
    _add_block(doc, BODY, BODY_SIZE)
    _add_block(doc, "1.2 Pentingnya Jaringan", HEADING_SIZE)
    _add_block(doc, BODY, BODY_SIZE)
    _add_block(doc, "Bab 2: Virtual LAN", HEADING_SIZE)
    _add_block(doc, "2.1 Pengertian VLAN", HEADING_SIZE)
    _add_block(doc, VLAN_BODY, BODY_SIZE)
    _add_block(doc, "2.2 Manfaat VLAN", HEADING_SIZE)
    _add_block(doc, VLAN_BODY, BODY_SIZE)
    _add_block(doc, "Bab 3: Routing", HEADING_SIZE)
    _add_block(doc, "3.1 Konsep Dasar Routing", HEADING_SIZE)
    _add_block(doc, ROUTING_BODY, BODY_SIZE)
    _add_block(doc, "Bab 4: Troubleshooting", HEADING_SIZE)
    _add_block(doc, TROUBLESHOOTING_BODY, BODY_SIZE)

    doc.save(str(path))
    doc.close()
    return path


def _add_block(doc: fitz.Document, text: str, fontsize: float) -> None:
    """Tulis paragraf dengan wrap; buat halaman baru jika overflow."""
    if doc.page_count == 0:
        doc.new_page()  # wajib: doc[-1] pada dokumen kosong bisa hang (bug PyMuPDF)
    page = doc[-1]
    rect = fitz.Rect(MARGIN, MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN)
    while True:
        remaining = page.insert_textbox(rect, text, fontsize=fontsize, fontname="helv")
        if remaining >= 0:
            break
        page = doc.new_page()
        rect = fitz.Rect(MARGIN, MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN)


if __name__ == "__main__":
    out = make_sample_pdf("tests/sample_materi_jaringan.pdf")
    print(f"Sample PDF dibuat: {out}")
