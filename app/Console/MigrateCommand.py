"""CLI Command for Database Migrations (migrate, migrate:fresh, migrate:reset)."""

from __future__ import annotations

import argparse
import importlib
import sys

from app.Core.Config import Settings
from app.Core.Database import get_connection
from database.seeders import DatabaseSeeder

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MIGRATIONS = [
    ("001_create_sessions_table", "database.migrations.001_create_sessions_table"),
    ("002_create_documents_table", "database.migrations.002_create_documents_table"),
    ("003_create_learning_tables", "database.migrations.003_create_learning_tables"),
    ("004_create_annotations_table", "database.migrations.004_create_annotations_table"),
]


def run(args: list[str], fresh: bool = False, reset: bool = False, seed: bool = False) -> None:
    parser = argparse.ArgumentParser(description="Run Database Migrations")
    parser.add_argument("--seed", action="store_true", help="Run seeders after migration")
    opts, _ = parser.parse_known_args(args)
    should_seed = seed or opts.seed

    settings = Settings()
    conn = get_connection(settings.db_path)

    if fresh or reset:
        print("[*] Dropping all database tables...")
        for name, mod_path in reversed(MIGRATIONS):
            try:
                mod = importlib.import_module(mod_path)
                mod.down(conn)
                print(f"  [-] Rolled back: {name}")
            except Exception as exc:
                print(f"  [x] Failed rolling back {name}: {exc}")
        conn.commit()

        if reset:
            print("[+] Database reset complete.")
            return

    print("[*] Running database migrations...")
    for name, mod_path in MIGRATIONS:
        try:
            mod = importlib.import_module(mod_path)
            mod.up(conn)
            print(f"  [+] Migrated: {name}")
        except Exception as exc:
            print(f"  [x] Migration error in {name}: {exc}")
    conn.commit()
    print("[+] All migrations executed successfully.")

    if should_seed:
        print("[*] Seeding database...")
        DatabaseSeeder.run(conn)
        print("[+] Database seeding complete.")
