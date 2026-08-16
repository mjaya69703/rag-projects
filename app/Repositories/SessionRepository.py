"""Session and Message repository for SQLite data store."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from app.Repositories.BaseRepository import BaseRepository


class SessionRepository(BaseRepository):
    """Repository handling sessions, messages, and session summaries."""

    def create_session(self, title: str = "New Chat") -> dict:
        session_id = uuid.uuid4().hex
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
        return {"id": session_id, "title": title, "created_at": now, "updated_at": now}

    def list_sessions(self) -> list[dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def rename_session(self, session_id: str, title: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title.strip() or "New Chat", self.now, session_id),
            )
        return cur.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0

    def touch_session(self, session_id: str) -> None:
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (self.now, session_id),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> dict:
        now = self.now
        src_json = json.dumps(sources) if sources else None
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, sources, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, src_json, now),
            )
            msg_id = cur.lastrowid
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "sources": sources,
            "created_at": now,
        }

    def get_messages(self, session_id: str, limit: int | None = None) -> list[dict]:
        with self.get_conn() as conn:
            if limit:
                rows = conn.execute(
                    "SELECT id, session_id, role, content, sources, created_at "
                    "FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
                rows = list(reversed(rows))
            else:
                rows = conn.execute(
                    "SELECT id, session_id, role, content, sources, created_at "
                    "FROM messages WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d["sources"]:
                d["sources"] = json.loads(d["sources"])
            result.append(d)
        return result

    def get_message_count(self, session_id: str) -> int:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row["c"] if row else 0

    def get_summary(self, session_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT session_id, summary_text, last_message_index, created_at "
                "FROM session_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_summary(
        self, session_id: str, summary_text: str, last_message_index: int
    ) -> None:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO session_summaries "
                "(session_id, summary_text, last_message_index, created_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "summary_text = excluded.summary_text, "
                "last_message_index = excluded.last_message_index, "
                "created_at = excluded.created_at",
                (session_id, summary_text, last_message_index, now),
            )

    def delete_messages_older_than(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self.get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM messages WHERE created_at < ?",
                (cutoff,),
            )
            deleted = cur.rowcount
            conn.execute(
                "DELETE FROM sessions WHERE id NOT IN (SELECT DISTINCT session_id FROM messages) "
                "AND updated_at < ?",
                (cutoff,),
            )
        return deleted

    def delete_all_user_data(self) -> dict[str, int]:
        with self.get_conn() as conn:
            cur_msg = conn.execute("DELETE FROM messages")
            msg_count = cur_msg.rowcount
            cur_sess = conn.execute("DELETE FROM sessions")
            sess_count = cur_sess.rowcount
            conn.execute("DELETE FROM session_summaries")
            cur_audit = conn.execute("DELETE FROM audit_log")
            audit_count = cur_audit.rowcount
        return {
            "messages_deleted": msg_count,
            "sessions_deleted": sess_count,
            "audit_log_deleted": audit_count,
        }
