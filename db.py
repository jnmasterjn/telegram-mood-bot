import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from utils import today_local


DATABASE_URL = os.getenv("DATABASE_URL", "")


@contextmanager
def _connect():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    first_name TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mood_logs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    emoji TEXT,
                    label TEXT,
                    tags TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, date)
                )
            """)


def upsert_user(user_id: str, chat_id: str, first_name: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, chat_id, first_name, created_at, last_seen_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    chat_id = EXCLUDED.chat_id,
                    first_name = EXCLUDED.first_name,
                    last_seen_at = EXCLUDED.last_seen_at
            """, (user_id, chat_id, first_name, now, now))


def list_users() -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY created_at")
            return cur.fetchall()


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone()


def save_mood(
    *,
    user_id: str,
    log_date: date,
    score: int,
    emoji: str = "",
    label: str = "",
    tags: list[str] | None = None,
    note: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(tags or [])
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mood_logs
                    (user_id, date, score, emoji, label, tags, note, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, date) DO UPDATE SET
                    score = EXCLUDED.score,
                    emoji = EXCLUDED.emoji,
                    label = EXCLUDED.label,
                    tags = EXCLUDED.tags,
                    note = CASE
                        WHEN EXCLUDED.note = '' THEN mood_logs.note
                        ELSE EXCLUDED.note
                    END,
                    updated_at = EXCLUDED.updated_at
            """, (user_id, log_date.isoformat(), score, emoji, label, tags_json, note, now, now))


def delete_log(user_id: str, log_date: date) -> bool:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM mood_logs WHERE user_id = %s AND date = %s",
                (user_id, log_date.isoformat()),
            )
            return cur.rowcount > 0


def clear_note(user_id: str, log_date: date) -> bool:
    row = get_day(user_id, log_date)
    if not row:
        return False
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE mood_logs SET note = '', updated_at = %s WHERE user_id = %s AND date = %s",
                (datetime.now(timezone.utc).isoformat(), user_id, log_date.isoformat()),
            )
    return True


def append_note(user_id: str, log_date: date, note: str) -> bool:
    row = get_day(user_id, log_date)
    if not row:
        return False
    current = row["note"] or ""
    next_note = note if not current else f"{current}\n{note}"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE mood_logs SET note = %s, updated_at = %s WHERE user_id = %s AND date = %s",
                (next_note, datetime.now(timezone.utc).isoformat(), user_id, log_date.isoformat()),
            )
    return True


def get_day(user_id: str, log_date: date) -> dict | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM mood_logs WHERE user_id = %s AND date = %s",
                (user_id, log_date.isoformat()),
            )
            return cur.fetchone()


def get_month(user_id: str, year: int, month: int) -> list[dict]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM mood_logs
                WHERE user_id = %s AND date >= %s AND date < %s
                ORDER BY date
            """, (user_id, start.isoformat(), end.isoformat()))
            return cur.fetchall()


def get_recent(user_id: str, days: int = 7) -> list[dict]:
    end = today_local()
    start = end - timedelta(days=days - 1)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM mood_logs
                WHERE user_id = %s AND date >= %s AND date <= %s
                ORDER BY date
            """, (user_id, start.isoformat(), end.isoformat()))
            return cur.fetchall()


def row_to_dict(row: dict) -> dict[str, Any]:
    data = dict(row)
    data["tags"] = json.loads(data["tags"] or "[]")
    return data
