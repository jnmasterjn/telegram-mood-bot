import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from utils import today_local


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "mood.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                first_name TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                score INTEGER NOT NULL,
                emoji TEXT,
                label TEXT,
                sleep REAL,
                tags TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, date)
            )
            """
        )


def upsert_user(user_id: str, chat_id: str, first_name: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, chat_id, first_name, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                first_name = excluded.first_name,
                last_seen_at = excluded.last_seen_at
            """,
            (user_id, chat_id, first_name, now, now),
        )


def list_users() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()


def save_mood(
    *,
    user_id: str,
    log_date: date,
    score: int,
    emoji: str = "",
    label: str = "",
    sleep: float | None = None,
    tags: list[str] | None = None,
    note: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(tags or [])
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO mood_logs
                (user_id, date, score, emoji, label, sleep, tags, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                score = excluded.score,
                emoji = excluded.emoji,
                label = excluded.label,
                sleep = excluded.sleep,
                tags = excluded.tags,
                note = CASE
                    WHEN excluded.note = '' THEN mood_logs.note
                    ELSE excluded.note
                END,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                log_date.isoformat(),
                score,
                emoji,
                label,
                sleep,
                tags_json,
                note,
                now,
                now,
            ),
        )


def append_note(user_id: str, log_date: date, note: str) -> bool:
    row = get_day(user_id, log_date)
    if not row:
        return False

    current = row["note"] or ""
    next_note = note if not current else f"{current}\n{note}"
    with _connect() as conn:
        conn.execute(
            "UPDATE mood_logs SET note = ?, updated_at = ? WHERE user_id = ? AND date = ?",
            (next_note, datetime.now(timezone.utc).isoformat(), user_id, log_date.isoformat()),
        )
    return True


def get_day(user_id: str, log_date: date) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM mood_logs WHERE user_id = ? AND date = ?",
            (user_id, log_date.isoformat()),
        ).fetchone()


def get_month(user_id: str, year: int, month: int) -> list[sqlite3.Row]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM mood_logs
            WHERE user_id = ? AND date >= ? AND date < ?
            ORDER BY date
            """,
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()


def get_recent(user_id: str, days: int = 7) -> list[sqlite3.Row]:
    end = today_local()
    start = end - timedelta(days=days - 1)
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM mood_logs
            WHERE user_id = ? AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["tags"] = json.loads(data["tags"] or "[]")
    return data
