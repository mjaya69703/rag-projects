"""Test web push notification: VAPID, subscription store, send, endpoints."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Isolasi DB ke direktori sementara SEBELUM import app.main (override .env)
_TMP = tempfile.mkdtemp()
os.environ["PERSIST_DIR"] = str(Path(_TMP) / "chroma")
os.environ["UPLOAD_DIR"] = str(Path(_TMP) / "uploads")
os.environ["DB_PATH"] = str(Path(_TMP) / "chat.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app import learning, push
from app.main import app

ENDPOINT = "https://push.example.test/send/abc123"


def test_vapid_keys_generate_and_persist(tmp_path: Path) -> None:
    priv1, pub1, subj = push.vapid_keys(tmp_path)
    assert priv1 and pub1
    assert subj == "mailto:admin@cortex.local"
    # persist: panggilan kedua memakai kunci yang sama
    priv2, pub2, _ = push.vapid_keys(tmp_path)
    assert priv1 == priv2 and pub1 == pub2
    assert (tmp_path / "vapid_private.pem").exists()


def test_subscription_crud(tmp_path: Path) -> None:
    db = tmp_path / "push.db"
    sub = push.save_subscription(
        db, ENDPOINT, p256dh="dHc=", auth="YXV0aA==",
        user_agent="pytest", remind_due=True, remind_hour=7,
    )
    assert sub["endpoint"] == ENDPOINT
    assert sub["remind_due"] == 1
    assert push.get_subscription(db, ENDPOINT)["p256dh"] == "dHc="
    assert len(push.list_subscriptions(db)) == 1

    # update preferensi
    updated = push.update_preferences(db, ENDPOINT, remind_due=False, remind_hour=19)
    assert updated["remind_due"] == 0
    assert updated["remind_hour"] == 19

    # unsubscribe
    assert push.unsubscribe(db, ENDPOINT) is True
    assert push.get_subscription(db, ENDPOINT) is None
    assert push.unsubscribe(db, ENDPOINT) is False


def test_due_reminder_payload(tmp_path: Path) -> None:
    db = tmp_path / "reminder.db"
    learning.create_custom_card(db, "Apa itu VLAN?", "Partisi broadcast.", "materi.pdf")
    payload = push.due_reminder_payload(db)
    assert payload is not None
    assert "1 kartu" in payload["title"]
    assert payload["url"] == "/flashcards"

    # tidak ada kartu due → None
    empty = tmp_path / "empty.db"
    assert push.due_reminder_payload(empty) is None


def test_weak_spots_reminder_payload(tmp_path: Path) -> None:
    from app import db as app_db
    db = tmp_path / "weak.db"
    app_db.init_db(db)
    with learning._conn_learning(db) as conn:
        conn.execute(
            "INSERT INTO review_cards (card_id, source, question, answer, lapses, next_due, created_at) "
            "VALUES ('r1', 'jaringan.pdf', 'OSPF Routing', 'ans', 3, '2026-08-01', '2026-08-01T00:00:00')"
        )
    payload = push.weak_spots_reminder_payload(db)
    assert payload is not None
    assert "Titik Lemah" in payload["title"]
    assert "OSPF Routing" in payload["body"]
    assert payload["url"] == "/quiz"


def test_inactivity_streak_payload(tmp_path: Path) -> None:
    from app import db as app_db
    from datetime import timedelta
    db = tmp_path / "streak.db"
    app_db.init_db(db)
    sess = app_db.create_session(db, title="Test")
    old_time = (datetime.now() - timedelta(days=3)).isoformat()
    with app_db._conn(db) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
            (sess["id"], "user", "Halo", "[]", old_time),
        )
    payload = push.inactivity_streak_payload(db, days_threshold=2)
    assert payload is not None
    assert "Streak" in payload["title"]
    assert payload["url"] == "/quiz"


def test_repeated_questions_challenge_payload(tmp_path: Path) -> None:
    from app import db as app_db
    db = tmp_path / "rep.db"
    app_db.init_db(db)
    sess = app_db.create_session(db, title="Test")
    app_db.add_message(db, sess["id"], "user", "bagaimana cara routing ospf?")
    app_db.add_message(db, sess["id"], "user", "bagaimana cara routing ospf?")
    payload = push.repeated_questions_challenge_payload(db, days=7, min_hits=2)
    assert payload is not None
    assert "Konsep" in payload["title"]
    assert "ospf" in payload["body"].lower()
    assert payload["url"] == "/quiz"


def test_daily_challenge_payload(tmp_path: Path) -> None:
    from app import db as app_db
    db = tmp_path / "daily.db"
    app_db.init_db(db)
    app_db.register_document(db, "Materi_AI.pdf", status="ready")
    payload = push.daily_challenge_payload(db)
    assert payload is not None
    assert "Tantangan" in payload["title"]
    assert "Materi_AI.pdf" in payload["body"]
    assert payload["url"] == "/quiz"


def test_smart_daily_reminder_payload_priority(tmp_path: Path) -> None:
    from app import db as app_db
    db = tmp_path / "smart.db"
    app_db.init_db(db)
    app_db.register_document(db, "Cloud.pdf", status="ready")

    # 1. Saat ada kartu due -> prioritas flashcards
    learning.create_custom_card(db, "Q1", "A1", "Cloud.pdf")
    payload1 = push.smart_daily_reminder_payload(db)
    assert payload1 is not None
    assert "flashcard" in payload1["title"].lower()

    # Hapus flashcards -> fallback ke daily challenge
    with learning._conn_learning(db) as conn:
        conn.execute("DELETE FROM review_cards")
    payload2 = push.smart_daily_reminder_payload(db)
    assert payload2 is not None
    assert "Tantangan" in payload2["title"]





def test_send_notification_ok(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "push.db"
    push.save_subscription(db, ENDPOINT, p256dh="dHc=", auth="YXV0aA==")
    sub = push.get_subscription(db, ENDPOINT)

    calls: dict = {}

    def fake_webpush(**kwargs):
        calls["payload"] = kwargs["data"]
        calls["vapid"] = kwargs["vapid_private_key"]
        return None

    monkeypatch.setattr("pywebpush.webpush", fake_webpush)
    assert push.send_notification(db, sub, title="T", body="B", url="/") is True
    assert "T" in calls["payload"] and "B" in calls["payload"]
    assert calls["vapid"]


def test_send_notification_expired_unsubscribes(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "push.db"
    push.save_subscription(db, ENDPOINT, p256dh="dHc=", auth="YXV0aA==")

    from pywebpush import WebPushException

    class FakeResponse:
        status_code = 410

    def failing_webpush(**kwargs):
        raise WebPushException("gone", response=FakeResponse())

    monkeypatch.setattr("pywebpush.webpush", failing_webpush)
    sub = push.get_subscription(db, ENDPOINT)
    assert push.send_notification(db, sub, title="T", body="B") is False
    assert push.get_subscription(db, ENDPOINT) is None, "subscription expired harus dihapus"


def test_push_endpoints(monkeypatch) -> None:
    """Endpoint push: public key, subscribe, preferensi, test, unsubscribe."""
    with TestClient(app) as client:
        # public key tersedia
        resp = client.get("/push/vapid-public-key")
        assert resp.status_code == 200
        assert resp.json()["public_key"]

        # subscribe
        resp = client.post(
            "/push/subscribe",
            json={
                "endpoint": ENDPOINT,
                "keys": {"p256dh": "dHc=", "auth": "YXV0aA=="},
                "user_agent": "pytest",
                "remind_due": True,
                "remind_hour": 8,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["subscription"]["remind_due"] == 1

        # preferensi
        resp = client.post(
            "/push/preferences",
            json={"endpoint": ENDPOINT, "remind_due": False, "remind_hour": 21},
        )
        assert resp.status_code == 200
        assert resp.json()["subscription"]["remind_hour"] == 21

        # kirim tes — webpush dimock
        monkeypatch.setattr(
            "pywebpush.webpush", lambda **kw: None
        )
        resp = client.post("/push/test", json={"endpoint": ENDPOINT})
        assert resp.status_code == 200
        assert resp.json()["sent"] is True

        # unsubscribe
        resp = client.request("DELETE", "/push/subscribe", json={"endpoint": ENDPOINT})
        assert resp.status_code == 200
        resp = client.request("DELETE", "/push/subscribe", json={"endpoint": ENDPOINT})
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
