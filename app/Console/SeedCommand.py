"""CLI Command for Database Seeding (db:seed)."""

from __future__ import annotations

from app.Core.Config import Settings
from app.Core.Database import get_connection
from database.seeders import DatabaseSeeder


def run(args: list[str]) -> None:
    settings = Settings()
    conn = get_connection(settings.db_path)
    print("🌱 Running database seeders...")
    DatabaseSeeder.run(conn)
    print("✅ Seeding complete.")
