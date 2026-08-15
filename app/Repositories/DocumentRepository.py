"""Document, Category, and Audit Log repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional
from app.Repositories.BaseRepository import BaseRepository


class DocumentRepository(BaseRepository):
    """Repository handling document registries, categories, deleted docs, and audit logs."""

    # ------------------------------------------------------------------
    # Document Registry (Lifecycle)
    # ------------------------------------------------------------------
    def doc_upsert(
        self,
        source: str,
        *,
        job_id: str = "",
        kind: str = "file",
        file_path: str = "",
        checksum: str = "",
        size_bytes: int = 0,
        category: str = "Umum",
        status: str = "queued",
        chunks: int = 0,
        error: str = "",
    ) -> dict:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO documents "
                "(source, job_id, kind, file_path, checksum, size_bytes, category, "
                " status, chunks, error, version, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(source) DO UPDATE SET "
                "job_id = CASE WHEN excluded.job_id != '' THEN excluded.job_id ELSE documents.job_id END, "
                "kind = excluded.kind, "
                "file_path = CASE WHEN excluded.file_path != '' THEN excluded.file_path ELSE documents.file_path END, "
                "checksum = CASE WHEN excluded.checksum != '' THEN excluded.checksum ELSE documents.checksum END, "
                "size_bytes = CASE WHEN excluded.size_bytes > 0 THEN excluded.size_bytes ELSE documents.size_bytes END, "
                "category = CASE WHEN excluded.category != 'Umum' THEN excluded.category ELSE documents.category END, "
                "status = excluded.status, "
                "chunks = excluded.chunks, "
                "error = excluded.error, "
                "version = documents.version + 1, "
                "updated_at = excluded.updated_at",
                (source, job_id, kind, file_path, checksum, size_bytes, category,
                 status, chunks, error, now, now),
            )
        return self.doc_get(source) or {}

    def doc_get(self, source: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE source = ?", (source,)).fetchone()
        return dict(row) if row else None

    def doc_list(self, status: str | None = None, category: str | None = None) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM documents {where} ORDER BY updated_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def doc_set_status(
        self,
        source: str,
        status: str,
        *,
        chunks: int | None = None,
        error: str | None = None,
    ) -> None:
        now = self.now
        sets = ["status = ?", "updated_at = ?"]
        params: list[object] = [status, now]
        if chunks is not None:
            sets.append("chunks = ?")
            params.append(chunks)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        params.append(source)
        with self.get_conn() as conn:
            conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE source = ?", params)

    def doc_delete(self, source: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute("DELETE FROM documents WHERE source = ?", (source,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Deleted Documents & Categories
    # ------------------------------------------------------------------
    def mark_document_deleted(self, source: str) -> None:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO deleted_documents (source, deleted_at) VALUES (?, ?) "
                "ON CONFLICT(source) DO UPDATE SET deleted_at = excluded.deleted_at",
                (source, now),
            )

    def unmark_document_deleted(self, source: str) -> None:
        with self.get_conn() as conn:
            conn.execute("DELETE FROM deleted_documents WHERE source = ?", (source,))

    def is_document_deleted(self, source: str) -> bool:
        with self.get_conn() as conn:
            row = conn.execute("SELECT 1 FROM deleted_documents WHERE source = ?", (source,)).fetchone()
        return row is not None

    def list_deleted_documents(self) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT source, deleted_at FROM deleted_documents ORDER BY deleted_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_document_category(self, source: str, category: str) -> None:
        now = self.now
        cat = category.strip() or "Umum"
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO document_categories (source, category, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(source) DO UPDATE SET category = excluded.category, updated_at = excluded.updated_at",
                (source, cat, now),
            )
            conn.execute(
                "UPDATE documents SET category = ?, updated_at = ? WHERE source = ?",
                (cat, now, source),
            )

    def get_document_category(self, source: str) -> str:
        with self.get_conn() as conn:
            row = conn.execute("SELECT category FROM document_categories WHERE source = ?", (source,)).fetchone()
            if row:
                return row["category"]
            row_doc = conn.execute("SELECT category FROM documents WHERE source = ?", (source,)).fetchone()
            if row_doc and row_doc["category"]:
                return row_doc["category"]
        return "Umum"

    def list_document_categories(self) -> dict[str, str]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT source, category FROM document_categories").fetchall()
        return {r["source"]: r["category"] for r in rows}

    # ------------------------------------------------------------------
    # Audit Log
    # ------------------------------------------------------------------
    def log_audit_event(
        self,
        actor: str,
        action: str,
        ip: str = "",
        status: int = 200,
        duration_ms: float = 0.0,
    ) -> None:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, actor, action, ip, status, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, actor, action, ip, status, duration_ms),
            )

    def get_audit_logs(self, limit: int = 100) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT id, ts, actor, action, ip, status, duration_ms "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [dict(r) for r in rows]
