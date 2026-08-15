"""Parsers package."""

from app.Services.Parsers.MarkdownParser import parse_markdown
from app.Services.Parsers.OfficeParser import parse_docx, parse_html, parse_pptx
from app.Services.Parsers.PdfParser import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    NO_HEADING_LABEL,
    Chunk,
    PageText,
    extract_pages,
    parse_pdf,
)
from app.Services.Parsers.UrlParser import (
    AntiBotBlock,
    SSRFBlockedError,
    URLFetchError,
    check_url,
    fetch_url_text,
    html_to_text,
    is_blocked_ip,
    parse_url,
    resolve_host,
)

__all__ = [
    "Chunk",
    "PageText",
    "extract_pages",
    "parse_pdf",
    "parse_markdown",
    "parse_docx",
    "parse_pptx",
    "parse_html",
    "parse_url",
    "fetch_url_text",
    "html_to_text",
    "check_url",
    "resolve_host",
    "is_blocked_ip",
    "SSRFBlockedError",
    "URLFetchError",
    "AntiBotBlock",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "NO_HEADING_LABEL",
]
