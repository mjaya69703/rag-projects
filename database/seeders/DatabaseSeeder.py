"""Main Database Seeder."""

import sqlite3

from database.seeders import GlossarySeeder, SampleCardSeeder


def run(conn: sqlite3.Connection) -> None:
    print("  [+] Seeding Glossary terms...")
    n_terms = GlossarySeeder.run(conn)
    print(f"      + {n_terms} glossary terms seeded.")

    print("  [+] Seeding Sample Flashcards...")
    n_cards = SampleCardSeeder.run(conn)
    print(f"      + {n_cards} sample review cards seeded.")
