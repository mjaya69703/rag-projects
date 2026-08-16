"""Telegram Bot Integration."""

from __future__ import annotations

import logging

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
except ImportError:
    _PTB_AVAILABLE = False

from app.Core.Config import MAX_UPLOAD_MB, Settings
from app.Services.Parsers.PdfParser import parse_pdf
from app.Services.RagService import RagService, Source

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


def format_sources(sources: list[Source]) -> str:
    if not sources:
        return ""
    lines = ["\n\n📚 *Sumber:*"]
    for s in sources:
        lines.append(f"• *{s.source}* (hal. {s.page}) — _{s.heading}_")
    return "\n".join(lines)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(START_TEXT)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def handle_documents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    engine: RagService = context.bot_data["engine"]
    docs = engine.vector_repo.list_all_documents()
    if not docs:
        await update.message.reply_text("Belum ada dokumen yang terindeks.")
        return
    text = "📄 *Dokumen terindeks:*\n" + "\n".join(f"• `{d}`" for d in docs)
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_query_text(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    if not update.message:
        return
    if not question.strip():
        await update.message.reply_text("Ketik pertanyaan setelah perintah /query.")
        return
    engine: RagService = context.bot_data["engine"]
    await update.message.chat.send_action("typing")
    try:
        ans = engine.query(question.strip())
        reply = ans.answer + format_sources(ans.sources)
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error answering query via telegram")
        await update.message.reply_text(f"Maaf, terjadi kesalahan: {exc}")


async def handle_query_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else ""
    await handle_query_text(update, context, text)


async def handle_plain_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        await handle_query_text(update, context, update.message.text)


async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return
    doc = update.message.document
    if not (doc.file_name or "").lower().endswith(".pdf"):
        await update.message.reply_text("Hanya file PDF yang didukung saat ini.")
        return
    if doc.file_size and doc.file_size > MAX_UPLOAD_MB * 1024 * 1024:
        await update.message.reply_text(f"Ukuran file melebihi batas {MAX_UPLOAD_MB}MB.")
        return

    settings: Settings = context.bot_data["settings"]
    engine: RagService = context.bot_data["engine"]
    await update.message.reply_text(f"Menerima `{doc.file_name}`... sedang mengunduh dan mengindeks.", parse_mode="Markdown")

    file_obj = await context.bot.get_file(doc.file_id)
    save_path = settings.upload_dir / (doc.file_name or "document.pdf")
    await file_obj.download_to_drive(custom_path=save_path)

    try:
        chunks = parse_pdf(save_path, source_name=doc.file_name)
        n = engine.vector_repo.add_documents(chunks, source=doc.file_name or "document.pdf")
        await update.message.reply_text(f"✅ Berhasil mengindeks *{doc.file_name}* ({n} chunk).", parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error indexing telegram PDF")
        await update.message.reply_text(f"❌ Gagal mengindeks: {exc}")


def build_telegram_app(token: str, engine: RagService, settings: Settings):
    if not _PTB_AVAILABLE:
        raise RuntimeError("python-telegram-bot belum terinstall.")
    app = Application.builder().token(token).build()
    app.bot_data["engine"] = engine
    app.bot_data["settings"] = settings
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("documents", handle_documents))
    app.add_handler(CommandHandler("query", handle_query_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document_upload))
    return app
