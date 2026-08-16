"""Base repository providing database connections and transaction support."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.Core.Config import config
from app.Core.Database import get_connection, now_utc


class BaseRepository:
    """Base repository class."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or config.db_path)

    def get_conn(self) -> sqlite3.Connection:
        """Obtain a SQLite connection with foreign keys enabled."""
        return get_connection(self.db_path)

    @property
    def now(self) -> str:
        """Current ISO-8601 UTC timestamp."""
        return now_utc()
