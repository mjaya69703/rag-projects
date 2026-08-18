"""Web Push Notification — reminder belajar via browser push service.

- VAPID keys auto-generate & persist ke ``data/vapid_private.pem``;
  bisa di-override via env ``VAPID_PUBLIC_KEY`` / ``VAPID_PRIVATE_KEY`` /
  ``VAPID_SUBJECT``.
- Subscription disimpan di tabel SQLite sendiri (``push_subscriptions``).
- Reminder utama: kartu flashcard SM-2 yang jatuh tempo hari ini
  (``learning.due_cards``), dikirim sekali per hari per subscription.

Catatan: Push API butuh konteks aman (HTTPS) atau localhost di sisi
browser — di LAN HTTP biasa browser akan menolak izin notifikasi.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PUSH_SCHEMA = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
    endpoint      TEXT PRIMARY KEY,
    p256dh        TEXT NOT NULL,
    auth          TEXT NOT NULL,
    user_agent    TEXT NOT NULL DEFAULT '',
    remind_due    INTEGER NOT NULL DEFAULT 0,
    remind_hour   INTEGER NOT NULL DEFAULT 7,
    last_due_sent TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(PUSH_SCHEMA)
    return conn


# ----------------------------------------------------------------------
# VAPID keys
# ----------------------------------------------------------------------
def _public_key_b64(v: Any) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from py_vapid import b64urlencode

    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return b64urlencode(raw)


def vapid_keys(settings_dir: str | Path) -> tuple[str, str, str]:
    """Return (private_key_pem, public_key_b64url, subject). Generate & persist bila belum ada."""
    subject = os.getenv("VAPID_SUBJECT", "mailto:admin@cortex.local").strip()
    priv_env = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    pub_env = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    if priv_env and pub_env:
        return priv_env, pub_env, subject

    key_file = Path(settings_dir) / "vapid_private.pem"
    if key_file.exists():
        from py_vapid import Vapid

        v = Vapid.from_file(str(key_file))
        return _pem_str(v.private_pem()), _public_key_b64(v), subject

    from py_vapid import Vapid

    v = Vapid()
    v.generate_keys()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        key_file.write_bytes(v.private_pem())
    except TypeError:
        key_file.write_text(v.private_pem(), encoding="utf-8")
    logger.info("VAPID keys dibuat: %s", key_file)
    return _pem_str(v.private_pem()), _public_key_b64(v), subject


def _pem_str(data: Any) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


# ----------------------------------------------------------------------
# Subscription store
# ----------------------------------------------------------------------
def save_subscription(
    db_path: str | Path,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
    remind_due: bool = False,
    remind_hour: int = 7,
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT INTO push_subscriptions "
            "(endpoint, p256dh, auth, user_agent, remind_due, remind_hour, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "p256dh = excluded.p256dh, auth = excluded.auth, "
            "user_agent = excluded.user_agent, updated_at = excluded.updated_at",
            (endpoint, p256dh, auth, user_agent, 1 if remind_due else 0,
             max(0, min(23, int(remind_hour))), now, now),
        )
        row = conn.execute(
            "SELECT * FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        ).fetchone()
    return dict(row)


def get_subscription(db_path: str | Path, endpoint: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        ).fetchone()
    return dict(row) if row else None


def list_subscriptions(db_path: str | Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM push_subscriptions ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def unsubscribe(db_path: str | Path, endpoint: str) -> bool:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        return cur.rowcount > 0


def update_preferences(
    db_path: str | Path, endpoint: str, remind_due: bool | None,
    remind_hour: int | None,
) -> dict | None:
    sets, params = [], []
    if remind_due is not None:
        sets.append("remind_due = ?")
        params.append(1 if remind_due else 0)
    if remind_hour is not None:
        sets.append("remind_hour = ?")
        params.append(max(0, min(23, int(remind_hour))))
    if not sets:
        return get_subscription(db_path, endpoint)
    params.append(endpoint)
    sets.append("updated_at = ?")
    params.insert(-1, datetime.now().isoformat(timespec="seconds"))
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE push_subscriptions SET {', '.join(sets)} WHERE endpoint = ?",
            params,
        )
    return get_subscription(db_path, endpoint)


def mark_due_sent(db_path: str | Path, endpoint: str, date_str: str) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE push_subscriptions SET last_due_sent = ?, updated_at = ? "
            "WHERE endpoint = ?",
            (date_str, datetime.now().isoformat(timespec="seconds"), endpoint),
        )


def _vapid_private_param(settings_dir: str | Path) -> Any:
    """Return key_file path or Vapid instance or PEM string for pywebpush."""
    priv_env = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    if priv_env:
        if os.path.isfile(priv_env):
            return priv_env
        from py_vapid import Vapid

        try:
            return Vapid.from_pem(priv_env.encode("utf-8"))
        except Exception:
            return priv_env

    key_file = Path(settings_dir) / "vapid_private.pem"
    if key_file.exists():
        return str(key_file)

    # Bila belum ada file, generate_keys dipanggil oleh vapid_keys
    vapid_keys(settings_dir)
    return str(key_file)


# ----------------------------------------------------------------------
# Sending
# ----------------------------------------------------------------------
def send_notification(
    db_path: str | Path, sub: dict, title: str, body: str, url: str = "/"
) -> bool:
    """Kirim push ke satu subscription; hapus bila kedaluwarsa (404/410)."""
    try:
        from pywebpush import WebPushException, webpush

        _priv, _pub, subject = vapid_keys(Path(db_path).parent)
        private_key = _vapid_private_param(Path(db_path).parent)
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False),
            vapid_private_key=private_key,
            vapid_claims={"sub": subject},
            ttl=86400,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            unsubscribe(db_path, sub["endpoint"])
            logger.info("subscription kedaluwarsa dihapus: %s", sub["endpoint"])
        else:
            logger.warning("gagal kirim push (status=%s): %s", status, exc)
        return False
    except Exception:
        logger.exception("gagal kirim push ke %s", sub.get("endpoint", "?"))
        return False


def send_test(db_path: str | Path, sub: dict) -> bool:
    return send_notification(
        db_path, sub,
        title="🔔 Notifikasi Cortex Aktif",
        body="Notifikasi web push berfungsi. Selamat belajar!",
        url="/",
    )


def notify_all(
    db_path: str | Path, title: str, body: str, url: str = "/"
) -> int:
    """Kirim notifikasi ke seluruh subscription yang terdaftar."""
    subs = list_subscriptions(db_path)
    sent = 0
    for sub in subs:
        if send_notification(db_path, sub, title, body, url):
            sent += 1
    return sent


# ----------------------------------------------------------------------
# Reminder builders
# ----------------------------------------------------------------------
def due_reminder_payload(db_path: str | Path, limit: int = 30) -> dict | None:
    """Payload notifikasi 'kartu due hari ini' dari learning.due_cards."""
    try:
        from app import learning

        cards = learning.due_cards(db_path, limit=limit)
        if not cards:
            return None
        count = len(cards)
        first = cards[0].get("question", "")
        body = f"Kamu punya {count} kartu yang jatuh tempo"
        if first:
            body += f" — mulai dari: \"{first[:80]}\""
        return {"title": f"⏰ {count} kartu flashcard siap diulang", "body": body, "url": "/flashcards"}
    except Exception:
        logger.exception("gagal membuat due_reminder_payload")
        return None


def weak_spots_reminder_payload(db_path: str | Path, limit: int = 3) -> dict | None:
    """Payload notifikasi 'latihan titik lemah' dari learning.weak_spots."""
    try:
        from app import learning

        spots = learning.weak_spots(db_path, limit=limit)
        # Ambil materi dengan lapses > 0 atau wrong > 0 atau score > 0
        weak = [s for s in spots if s.get("topic") and (s.get("wrong", 0) > 0 or s.get("lapses", 0) > 0 or s.get("score", 0) > 0)]
        if not weak:
            return None
        sample = weak[:limit]
        topics = ", ".join(f"'{s['topic']}'" for s in sample if s.get("topic"))
        if not topics:
            return None
        count = len(weak)
        return {
            "title": "💡 Penguatan Titik Lemah Belajar",
            "body": f"Ada {count} materi yang perlu diperbaiki: {topics}. Uji kuis kilat sekarang!",
            "url": "/quiz",
        }
    except Exception:
        logger.exception("gagal membuat weak_spots_reminder_payload")
        return None


def inactivity_streak_payload(db_path: str | Path, days_threshold: int = 2) -> dict | None:
    """Payload notifikasi jika user tidak aktif belajar selama >= days_threshold hari."""
    try:
        dates: list[str] = []
        with _conn(db_path) as conn:
            # Cek aktivitas terakhir: pesan chat
            has_msgs = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'").fetchone()
            if has_msgs:
                row = conn.execute("SELECT created_at FROM messages ORDER BY created_at DESC LIMIT 1").fetchone()
                if row and row[0]:
                    dates.append(str(row[0]))

            # Cek kuis
            has_quiz = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_attempts'").fetchone()
            if has_quiz:
                row = conn.execute("SELECT created_at FROM quiz_attempts ORDER BY created_at DESC LIMIT 1").fetchone()
                if row and row[0]:
                    dates.append(str(row[0]))

            # Cek rating kartu flashcard / review
            has_cards = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_cards'").fetchone()
            if has_cards:
                row = conn.execute("SELECT next_due FROM review_cards ORDER BY next_due DESC LIMIT 1").fetchone()
                if row and row[0]:
                    dates.append(str(row[0]))

        if not dates:
            return None

        # Parse tanggal
        parsed_dates = []
        for d in dates:
            try:
                dt_str = d.replace("Z", "").split(".")[0]
                parsed_dates.append(datetime.fromisoformat(dt_str))
            except Exception:
                continue

        if not parsed_dates:
            return None

        latest = max(parsed_dates)
        delta_days = (datetime.now() - latest).days
        if delta_days >= days_threshold:
            return {
                "title": "🔥 Jaga Streak Belajar Kamu!",
                "body": f"Sudah {delta_days} hari kamu belum mengulang materi. Buka kuis kilat hari ini!",
                "url": "/quiz",
            }
        return None
    except Exception:
        logger.exception("gagal membuat inactivity_streak_payload")
        return None


def repeated_questions_challenge_payload(db_path: str | Path, days: int = 7, min_hits: int = 2) -> dict | None:
    """Payload notifikasi tantangan pemahaman untuk konsep yang sering ditanyakan."""
    try:
        from app import db

        repeated = db.repeated_questions(db_path, days=days, min_hits=min_hits)
        if not repeated:
            return None
        top = repeated[0]
        q_text = top.get("question") or top.get("canonical_query") or top.get("query") or ""
        if not q_text:
            return None
        hits = top.get("count") or top.get("hits", min_hits)
        return {
            "title": "🎯 Tantangan Penguasaan Konsep",
            "body": f"Kamu menanyakan \"{q_text[:70]}\" sebanyak {hits}x minggu ini. Uji pemahamanmu sekarang!",
            "url": "/quiz",
        }
    except Exception:
        logger.exception("gagal membuat repeated_questions_challenge_payload")
        return None


def daily_challenge_payload(db_path: str | Path) -> dict | None:
    """Payload notifikasi kuis kilat harian acak dari materi perpustakaan yang ada."""
    try:
        from app import db

        docs = db.list_document_registry(db_path)
        ready_docs = [d for d in docs if d.get("status") == "ready"]
        if not ready_docs:
            return None
        import random

        picked = random.choice(ready_docs)
        doc_name = picked.get("source", "Dokumen")
        name_clean = Path(doc_name).name
        return {
            "title": "🧠 Tantangan Kuis Harian",
            "body": f"Asah ingatanmu dari materi '{name_clean}'. Mulai 3 soal kuis kilat!",
            "url": "/quiz",
        }
    except Exception:
        logger.exception("gagal membuat daily_challenge_payload")
        return None


def smart_daily_reminder_payload(db_path: str | Path) -> dict | None:
    """Pilih 1 notifikasi harian paling bernilai sesuai prioritas cerdas."""
    # 1. Prioritas utama: Kartu flashcard due SM-2
    due_p = due_reminder_payload(db_path)
    if due_p:
        return due_p

    # 2. Prioritas kedua: Titik lemah materi (weak spots)
    weak_p = weak_spots_reminder_payload(db_path)
    if weak_p:
        return weak_p

    # 3. Prioritas ketiga: Penyelamat streak (jika >= 2 hari tidak aktif)
    streak_p = inactivity_streak_payload(db_path, days_threshold=2)
    if streak_p:
        return streak_p

    # 4. Prioritas keempat: Tantangan pertanyaan berulang
    rep_p = repeated_questions_challenge_payload(db_path)
    if rep_p:
        return rep_p

    # 5. Prioritas kelima: Daily challenge acak dari materi
    return daily_challenge_payload(db_path)


