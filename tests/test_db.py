"""Test layer database SQLite (sessions, messages, summaries).

Jalankan: python tests/test_db.py  atau  pytest tests/test_db.py -v
"""

from __future__ import annotations

import sys
import tempfile
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


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_session_crud(tmp_path)
        test_messages_and_limit(tmp_path)
        test_summary_save_get(tmp_path)
        test_delete_session_cascades_messages(tmp_path)
    print("\nSemua test DB PASS ✔")


if __name__ == "__main__":
    main()
