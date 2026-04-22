"""Postgres-backed course catalog.

Mirrors the public API of store/catalog.py (SQLite) exactly:
    init_db() · upsert(course_id, topic, payload) · list_all() · get(course_id)

Uses psycopg v3 with a module-level connection pool. The pool is lazy-init
so importing this module doesn't require DATABASE_URL to be set yet.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from psycopg_pool import ConnectionPool


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Required when STORAGE_BACKEND=postgres."
        )
    # LangGraph uses `postgresql+psycopg://` in some contexts; strip for raw psycopg.
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def _pool() -> ConnectionPool:
    # min_size=1, max_size=5 — small for MVP, bump when we scale.
    # open=True opens the pool eagerly on first use.
    return ConnectionPool(conninfo=_db_url(), min_size=1, max_size=5, open=True)


def init_db() -> None:
    """No-op for Postgres — schema is created by scripts/pg_migrate.py."""
    # Smoke-check the table exists so failures surface early.
    with _pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'courses'"
            )
            if cur.fetchone() is None:
                raise RuntimeError(
                    "courses table not found. Run: python scripts/pg_migrate.py"
                )


def upsert(course_id: str, topic: str, payload: dict[str, Any]) -> None:
    video_count = len(payload.get("videos", []))
    with _pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO courses (course_id, topic, video_count, created_at, payload)
                VALUES (%s, %s, %s, NOW(), %s::jsonb)
                ON CONFLICT (course_id) DO UPDATE SET
                    topic       = EXCLUDED.topic,
                    video_count = EXCLUDED.video_count,
                    payload     = EXCLUDED.payload
                """,
                (course_id, topic, video_count, json.dumps(payload)),
            )
        conn.commit()


def list_all() -> list[dict[str, Any]]:
    with _pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT course_id, topic, video_count, created_at "
                "FROM courses ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
    return [
        {
            "course_id": r[0],
            "topic": r[1],
            "video_count": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


def get(course_id: str) -> dict[str, Any] | None:
    with _pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT course_id, topic, video_count, created_at, payload "
                "FROM courses WHERE course_id = %s",
                (course_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "course_id": row[0],
        "topic": row[1],
        "video_count": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
        # psycopg v3 returns JSONB as dict already — no json.loads needed.
        "payload": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
    }
