"""Telegram bot: akses knowledge base dari HP via chat.

Command:
- /start, /help: instruksi
- /documents: daftar dokumen terindeks
- /query <teks>: tanya jawab
- pesan teks biasa: diperlakukan sebagai pertanyaan
- upload PDF: parse + index otomatis

Jalankan: .venv\\Scripts\\python -m app.telegram_bot
Token dari env TELEGRAM_BOT_TOKEN (kosong = bot tidak dijalankan, exit 0).
"""

from __future__ import annotations

import logging
from pathlib import Path

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

    _PTB_AVAILABLE = True
except ImportError:  # pragma: no cover - tergantung env mesin
    _PTB_AVAILABLE = False

from app.config import MAX_UPLOAD_MB, Settings
from app.mcp_server import create_engine, format_sources
from app.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)

START_TEXT = (
    "Halo! Saya bot knowledge base kamu. 📚\n\n"
    "Yang bisa saya lakukan:\n"
    "- Tanya jawab isi dokumenmu (langsung ketik pertanyaannya)\n"
    "- /query <pertanyaan> — tanya dengan perintah eksplisit\n"
    "- /documents — lihat daftar dokumen terindeks\n"
    "- Kirim file PDF — biar saya index otomatis\n\n"
    "Ketik /help untuk daftar perintah lengkap."
)

HELP_TEXT = (
    "Perintah yang tersedia:\n"
    "/start — sapaan & pengenalan\n"
    "/documents — daftar dokumen terindeks\n"
    "/query <teks> — jawab pertanyaan berdasarkan dokumen\n"
    "/help — daftar perintah ini\n\n"
    "Tips:\n"
    "- Ketik pertanyaan langsung tanpa perintah, contoh: \"Apa itu VLAN?\"\n"
    "- Kirim PDF untuk menambah dokumen ke knowledge base."
)


def _require_ptb() -> None:
    """SystemExit dengan instruksi bila python-telegram-bot belum terinstall."""
    if not _PTB_AVAILABLE:
        raise SystemExit(
            "python-telegram-bot belum terinstall — jalankan: "
            "pip install python-telegram-bot"
        )


def _trim(text: str, limit: int) -> str:
    """Potong teks panjang (Telegram batasi ~4096 char per pesan)."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n… (terpotong)"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_documents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    docs = create_engine().store.list_documents()
    if not docs:
        await update.message.reply_text(
            "Belum ada dokumen terindeks. Kirim PDF untuk mulai."
        )
        return
    lines = [f"📄 {d['source']} — {d['chunks']} chunk" for d in docs]
    await update.message.reply_text("Dokumen terindeks:\n" + "\n".join(lines))


async def _answer(update: Update, question: str) -> None:
    """Jawab pertanyaan via engine, balas dengan sumber ringkas."""
    if not question.strip():
        await update.message.reply_text(
            "Tulis pertanyaannya dulu, contoh: /query Apa itu VLAN?"
        )
        return
    answer = create_engine().query(question)
    text = _trim(answer.answer, 3000)
    if answer.sources:
        text += "\n\nSumber:\n" + _trim(format_sources(answer.sources), 1000)
    await update.message.reply_text(text)


async def cmd_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args or [])
    await _answer(update, question)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback: pesan teks biasa diperlakukan sebagai pertanyaan."""
    await _answer(update, update.message.text or "")


async def on_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Terima PDF, simpan ke upload_dir, lalu index ke ChromaDB."""
    settings = Settings()
    document = update.message.document
    filename = Path(document.file_name or "upload.pdf").name  # cegah path traversal
    if not filename.lower().endswith(".pdf"):
        await update.message.reply_text("Hanya file PDF yang didukung.")
        return
    if document.file_size and document.file_size > MAX_UPLOAD_MB * 1024 * 1024:
        await update.message.reply_text(f"File maksimal {MAX_UPLOAD_MB} MB.")
        return

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = settings.upload_dir / filename
    file = await document.get_file()
    await file.download_to_drive(pdf_path)

    try:
        chunks = parse_pdf(pdf_path, source=filename)
    except Exception as exc:
        logger.exception("Gagal memproses PDF: %s", filename)
        await update.message.reply_text(f"Gagal memproses PDF: {exc}")
        return
    if not chunks:
        await update.message.reply_text(
            "Tidak ada teks yang bisa diekstrak (PDF hasil scan?)."
        )
        return

    store = create_engine().store
    removed = store.delete_document(filename)  # upload ulang = replace
    n = store.add_documents(chunks, source=filename)
    extra = f" (menggantikan {removed} chunk lama)" if removed else ""
    await update.message.reply_text(f"✅ {filename} terindex: {n} chunk{extra}.")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jaring error global: log + balas pesan ramah, jangan crash."""
    logger.error("Bot error: %s", context.error, exc_info=context.error)
    chat = getattr(update, "effective_chat", None)
    if chat is not None:
        await chat.send_message(
            "⚠️ Terjadi kesalahan saat memproses permintaan. Coba lagi ya."
        )


def build_application(token: str) -> Application:
    """Bangun Application bot dengan semua handler terdaftar."""
    _require_ptb()
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("documents", cmd_documents))
    application.add_handler(CommandHandler("query", cmd_query))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("pdf"), on_pdf_upload)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message)
    )
    application.add_error_handler(on_error)
    return application


def main() -> int:
    """Jalankan bot. Tanpa token: print instruksi & exit 0 (tanpa error)."""
    settings = Settings()
    if not settings.telegram_bot_token:
        print(
            "TELEGRAM_BOT_TOKEN belum diisi di file .env — bot tidak dijalankan.\n"
            "Buat bot via @BotFather, lalu isi token di .env:\n"
            "TELEGRAM_BOT_TOKEN=<token>"
        )
        return 0
    _require_ptb()
    application = build_application(settings.telegram_bot_token)
    application.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
