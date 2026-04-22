"""Idempotent Postgres schema bootstrap for AdaptivAI.

Usage:
    python scripts/pg_migrate.py

Requires DATABASE_URL in .env.

Creates:
    1. `vector` extension (pgvector) — no-op if already present.
    2. `courses` table — mirrors catalog.sqlite schema, JSONB payload.
    3. LangGraph checkpointer tables — via AsyncPostgresSaver.setup().
    4. langchain_postgres PGVector tables are created lazily on first .add_texts(),
       so no upfront work needed there.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


COURSES_DDL = """
CREATE TABLE IF NOT EXISTS courses (
    course_id    TEXT PRIMARY KEY,
    topic        TEXT NOT NULL,
    video_count  INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload      JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS courses_created_at_idx ON courses (created_at DESC);
"""


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is not set. Add it to .env first.")
    return url


def run_sync() -> None:
    url = _db_url()
    # psycopg v3 accepts both postgresql:// and postgres:// schemes.
    print(f"Connecting to Postgres...")
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("  1. Enabling pgvector extension...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            print("  2. Creating courses table + index...")
            cur.execute(COURSES_DDL)

    print("Sync DDL complete.")


async def run_checkpointer_setup() -> None:
    url = _db_url()
    print("  3. Setting up LangGraph checkpointer tables...")
    # Note: LangGraph's AsyncPostgresSaver prefers the `postgresql://...` scheme
    # without the `+psycopg` SQLAlchemy suffix.
    clean_url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(clean_url) as saver:
        await saver.setup()
    print("Checkpointer setup complete.")


def main() -> None:
    # psycopg async requires SelectorEventLoop on Windows; ProactorEventLoop fails.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    run_sync()
    asyncio.run(run_checkpointer_setup())
    print("\nAll done. Database is ready.")
    print("Now set STORAGE_BACKEND=postgres in .env and run:")
    print('    python scripts/smoke_test.py "Docker basics"')


if __name__ == "__main__":
    main()
