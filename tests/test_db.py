"""Test layer database SQLite (sessions, messages, summaries).

Jalankan: python tests/test_db.py  atau  pytest tests/test_db.py -v
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db


def test_session_crud(tmp_path: Path) -> None:
    path = tmp_path / "chat.db"
    db.init_db(path)

    s = db.create_session(path)
    assert s["title"] == "New Chat"
    assert db.get_session(path, s["id"])["id"] == s["id"]

    sessions = db.list_sessions(path)
    assert len(sessions) == 1 and sessions[0]["id"] == s["id"]

    # rename
    assert db.rename_session(path, s["id"], "Belajar VLAN")
    assert db.get_session(path, s["id"])["title"] == "Belajar VLAN"

    # delete
    assert db.delete_session(path, s["id"])
    assert db.get_session(path, s["id"]) is None
    assert db.list_sessions(path) == []


def test_messages_and_limit(tmp_path: Path) -> None:
    path = tmp_path / "chat.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]

    for i in range(6):
        db.add_message(path, sid, "user" if i % 2 == 0 else "assistant", f"pesan {i}", [])

    assert db.message_count(path, sid) == 6

    all_msgs = db.get_messages(path, sid)
    assert len(all_msgs) == 6
    assert all_msgs[0]["content"] == "pesan 0"
    assert all_msgs[-1]["content"] == "pesan 5"

    last2 = db.get_messages(path, sid, limit=2)
    assert [m["content"] for m in last2] == ["pesan 4", "pesan 5"]

    tokens = db.estimate_tokens(path, sid)
    assert tokens > 0
    print(f"[OK] messages, limit, tokens_est={tokens}")


def test_summary_save_get(tmp_path: Path) -> None:
    path = tmp_path / "chat.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]

    assert db.get_summary(path, sid) is None
    db.save_summary(path, sid, "Ringkasan percakapan", 10)
    summ = db.get_summary(path, sid)
    assert summ["summary_text"] == "Ringkasan percakapan"
    assert summ["last_message_index"] == 10

    # update (upsert)
    db.save_summary(path, sid, "Ringkasan baru", 20)
    assert db.get_summary(path, sid)["summary_text"] == "Ringkasan baru"


def test_delete_session_cascades_messages(tmp_path: Path) -> None:
    path = tmp_path / "chat.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]
    db.add_message(path, sid, "user", "halo", [])
    db.add_message(path, sid, "assistant", "hai", [])
    assert db.message_count(path, sid) == 2
    db.delete_session(path, sid)
    assert db.get_messages(path, sid) == []


def test_repeated_questions(tmp_path: Path) -> None:
    """Termometer: pertanyaan user yang diulang, dalam window 7 hari."""
    path = tmp_path / "chat.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]

    db.add_message(path, sid, "user", "Apa itu VLAN?", [])
    db.add_message(path, sid, "assistant", "Jawaban.", [])
    db.add_message(path, sid, "user", "Apa itu VLAN?", [])  # diulang
    db.add_message(path, sid, "user", "bagaimana cara routing?", [])

    # Pesan lama (di luar window 7 hari, dalam window 30 hari)
    old = (datetime.now(UTC) - timedelta(days=29)).isoformat()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, sources, created_at) "
            "VALUES (?, 'user', 'Apa itu VLAN?', '[]', ?)",
            (sid, old),
        )

    rep = db.repeated_questions(path)
    assert len(rep) == 1
    assert rep[0]["question"] == "Apa itu VLAN?"
    assert rep[0]["count"] == 2
    assert rep[0]["last_asked"]

    # Pesan lama tidak dihitung: 2 baru + 1 lama tetap < 3 -> tidak lolos
    assert db.repeated_questions(path, min_hits=3) == []

    # Window diperlebar -> pesan lama ikut terhitung (2 baru + 1 lama)
    rep30 = db.repeated_questions(path, days=30)
    assert len(rep30) == 1 and rep30[0]["count"] == 3


def test_usage_summary(tmp_path: Path) -> None:
    """Konteks termometer: sesi aktif & jumlah pertanyaan dalam window."""
    path = tmp_path / "chat.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]
    sid2 = db.create_session(path)["id"]

    db.add_message(path, sid, "user", "Apa itu VLAN?", [])
    db.add_message(path, sid, "assistant", "Jawaban.", [])
    db.add_message(path, sid2, "user", "apa itu routing?", [])

    usage = db.usage_summary(path)
    assert usage["sessions_active"] == 2
    assert usage["questions"] == 2

    old = (datetime.now(UTC) - timedelta(days=29)).isoformat()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, sources, created_at) "
            "VALUES (?, 'user', 'pesan lama', '[]', ?)",
            (sid, old),
        )
    assert db.usage_summary(path)["questions"] == 2  # pesan lama diabaikan
    assert db.usage_summary(path, days=30)["questions"] == 3


def test_deleted_documents_tracking(tmp_path: Path) -> None:
    """Tracking dokumen yang dihapus: record -> list -> clear."""
    path = tmp_path / "chat.db"
    db.init_db(path)

    assert db.list_deleted_documents(path) == []
    db.record_deleted_document(path, "materi_lama.pdf")
    db.record_deleted_document(path, "modul_basi.pdf")
    deleted = db.list_deleted_documents(path)
    assert {d["source"] for d in deleted} == {"materi_lama.pdf", "modul_basi.pdf"}
    assert all(d["deleted_at"] for d in deleted)

    # upload ulang -> clear; record ulang dokumen yang sama -> replace (1 baris)
    db.clear_deleted_document(path, "materi_lama.pdf")
    assert {d["source"] for d in db.list_deleted_documents(path)} == {"modul_basi.pdf"}
    db.record_deleted_document(path, "modul_basi.pdf")
    assert len(db.list_deleted_documents(path)) == 1


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_session_crud(tmp_path)
        test_messages_and_limit(tmp_path)
        test_summary_save_get(tmp_path)
        test_delete_session_cascades_messages(tmp_path)
        test_repeated_questions(tmp_path)
        test_usage_summary(tmp_path)
        test_deleted_documents_tracking(tmp_path)
    print("\nSemua test DB PASS ✔")


if __name__ == "__main__":
    main()
