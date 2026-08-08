import logging
from pathlib import Path

from app.md_parser import parse_markdown
from app.office_parser import parse_docx, parse_html, parse_pptx
from app.pdf_parser import Chunk, parse_pdf

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".md",
    ".txt",
    ".markdown",
    ".docx",
    ".pptx",
    ".html",
    ".htm",
}
_TEXT_EXTENSIONS = {".md", ".txt", ".markdown"}


def is_supported(path: str | Path) -> bool:
    """True jika ekstensi file masuk daftar yang didukung watch-folder."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def get_category_for_path(upload_dir: str | Path, path: str | Path) -> str:
    """Dapatkan nama kategori dari nama subfolder di dalam upload_dir."""
    try:
        up_dir = Path(upload_dir).resolve()
        p = Path(path).resolve()
        rel = p.relative_to(up_dir)
        if len(rel.parts) > 1:
            return rel.parts[0]
    except Exception:
        pass
    return "Umum"


def parse_any(path: str | Path, source: str | None = None) -> list[Chunk]:
    """Dispatch parsing sesuai ekstensi file (pdf/markdown/office/html)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path, source=source)
    if ext in _TEXT_EXTENSIONS:
        return parse_markdown(path, source=source)
    if ext == ".docx":
        return parse_docx(path, source=source)
    if ext == ".pptx":
        return parse_pptx(path, source=source)
    if ext in {".html", ".htm"}:
        return parse_html(path, source=source)
    raise ValueError(
        f"Ekstensi tidak didukung: {ext!r} "
        f"(dukungan: {sorted(SUPPORTED_EXTENSIONS)})"
    )


def scan_pending(upload_dir: str | Path, indexed_sources: set[str]) -> list[Path]:
    """Daftar file di upload_dir (termasuk subfolder) yang belum terindeks."""
    upload_dir = Path(upload_dir)
    if not upload_dir.is_dir():
        return []

    indexed = set(indexed_sources)
    pending = [
        p
        for p in upload_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
        and p.name not in indexed
    ]
    pending.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return pending
