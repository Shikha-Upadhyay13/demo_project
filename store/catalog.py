"""SQLite-backed course catalog.

Payload is stored as JSON — one read per GET /api/courses/{id}.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

CATALOG_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "catalog.sqlite"))


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CATALOG_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                course_id    TEXT PRIMARY KEY,
                topic        TEXT NOT NULL,
                video_count  INTEGER NOT NULL,
                created_at   TEXT NOT NULL,
                payload      TEXT NOT NULL
            )
            """
        )


def upsert(course_id: str, topic: str, payload: dict[str, Any]) -> None:
    init_db()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO courses (course_id, topic, video_count, created_at, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                topic       = excluded.topic,
                video_count = excluded.video_count,
                payload     = excluded.payload
            """,
            (
                course_id,
                topic,
                len(payload.get("videos", [])),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload),
            ),
        )


def list_all() -> list[dict[str, Any]]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT course_id, topic, video_count, created_at FROM courses ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get(course_id: str) -> dict[str, Any] | None:
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT course_id, topic, video_count, created_at, payload FROM courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["payload"] = json.loads(out["payload"])
    return out
