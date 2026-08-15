"""Annotation and Glossary data repository."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, List, Optional
from app.Repositories.BaseRepository import BaseRepository


class AnnotationRepository(BaseRepository):
    """Repository handling document annotations and domain glossary terms."""

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    def create_annotation(
        self,
        source: str,
        chunk_id: str,
        text: str,
        page: int | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        ann_id = uuid.uuid4().hex
        now = self.now
        tags_json = json.dumps(tags or [])
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO annotations (id, source, chunk_id, page, text, tags, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ann_id, source, chunk_id, page, text, tags_json, now, now),
            )
        return {
            "id": ann_id,
            "source": source,
            "chunk_id": chunk_id,
            "page": page,
            "text": text,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }

    def list_annotations(
        self,
        source: str | None = None,
        tag: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM annotations {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            if tag and tag not in d["tags"]:
                continue
            result.append(d)
        return result

    def get_annotation(self, ann_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM annotations WHERE id = ?", (ann_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        return d

    def update_annotation(
        self,
        ann_id: str,
        text: str | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        now = self.now
        sets = ["updated_at = ?"]
        params: list[object] = [now]
        if text is not None:
            sets.append("text = ?")
            params.append(text)
        if tags is not None:
            sets.append("tags = ?")
            params.append(json.dumps(tags))
        params.append(ann_id)
        with self.get_conn() as conn:
            cur = conn.execute(f"UPDATE annotations SET {', '.join(sets)} WHERE id = ?", params)
            if cur.rowcount == 0:
                return None
        return self.get_annotation(ann_id)

    def delete_annotation(self, ann_id: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------
    def list_glossary(
        self,
        search: str = "",
        source: str | None = None,
        verified: bool | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if search.strip():
            like = f"%{search.strip()}%"
            clauses.append("(term LIKE ? OR definition LIKE ?)")
            params.extend([like, like])
        if source:
            clauses.append("source = ?")
            params.append(source)
        if verified is not None:
            clauses.append("verified = ?")
            params.append(int(verified))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 200)))
        with self.get_conn() as conn:
            rows = conn.execute(
                f"SELECT id, term, definition, source, page, category, verified, created_at, updated_at "
                f"FROM glossary_terms {where} ORDER BY term COLLATE NOCASE ASC LIMIT ?",
                params,
            ).fetchall()
        return [{**dict(row), "verified": bool(row["verified"])} for row in rows]

    def create_glossary_term(
        self,
        term: str,
        definition: str,
        source: str = "",
        page: int | None = None,
        category: str = "Umum",
        verified: bool = False,
    ) -> dict:
        now = self.now
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO glossary_terms "
                "(term, definition, source, page, category, verified, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (term.strip(), definition.strip(), source.strip(), page, category.strip() or "Umum",
                 int(verified), now, now),
            )
            term_id = cur.lastrowid
        return self.get_glossary_term(int(term_id)) or {}

    def get_glossary_term(self, term_id: int) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM glossary_terms WHERE id = ?", (term_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "verified": bool(row["verified"])}

    def update_glossary_term(
        self,
        term_id: int,
        term: str,
        definition: str,
        source: str = "",
        page: int | None = None,
        category: str = "Umum",
        verified: bool = False,
    ) -> dict | None:
        with self.get_conn() as conn:
            cur = conn.execute(
                "UPDATE glossary_terms SET term = ?, definition = ?, source = ?, page = ?, "
                "category = ?, verified = ?, updated_at = ? WHERE id = ?",
                (term.strip(), definition.strip(), source.strip(), page, category.strip() or "Umum",
                 int(verified), self.now, term_id),
            )
        return self.get_glossary_term(term_id) if cur.rowcount else None

    def delete_glossary_term(self, term_id: int) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))
        return cur.rowcount > 0
