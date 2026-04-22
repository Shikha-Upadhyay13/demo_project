"""Course Builder graph — runs once per new topic.

Linear: video_finder → transcript_fetcher → chunker_embedder → END.

Checkpointer is selected by STORAGE_BACKEND env var:
- sqlite (default) → SqliteSaver / AsyncSqliteSaver over checkpoints.sqlite
- postgres         → PostgresSaver / AsyncPostgresSaver via DATABASE_URL
"""
from __future__ import annotations

import os
import sqlite3
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from models.schemas import CourseState
from nodes.indexing import chunker_embedder
from nodes.video import transcript_fetcher, video_finder

_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite").strip().lower()
CHECKPOINT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints.sqlite"))


# ──────────────── Sync checkpointer ────────────────

@lru_cache(maxsize=1)
def _checkpointer():
    """Sync checkpointer for scripts that call `graph.invoke()`."""
    if _BACKEND == "postgres":
        import psycopg
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver
        # Long-lived connection; autocommit is required by LangGraph's postgres saver.
        conn = psycopg.connect(
            _pg_url(),
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        return PostgresSaver(conn)
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver
        # check_same_thread=False so FastAPI worker threads can share the connection.
        conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
        return SqliteSaver(conn)


# ──────────────── Async checkpointer ────────────────

_async_saver = None


async def _async_checkpointer():
    """Async checkpointer for FastAPI endpoints that stream via `graph.astream()`."""
    global _async_saver
    if _async_saver is not None:
        return _async_saver

    if _BACKEND == "postgres":
        import psycopg
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        # Long-lived async connection; autocommit + prepare_threshold=0 are required.
        conn = await psycopg.AsyncConnection.connect(
            _pg_url(),
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        _async_saver = AsyncPostgresSaver(conn)
    else:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        conn = await aiosqlite.connect(CHECKPOINT_DB, check_same_thread=False)
        _async_saver = AsyncSqliteSaver(conn)
    return _async_saver


def _pg_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Required when STORAGE_BACKEND=postgres."
        )
    # LangGraph's PostgresSaver uses plain postgresql:// (no +psycopg driver suffix).
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


# ──────────────── Graph ────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(CourseState)

    g.add_node("video_finder", video_finder)
    g.add_node("transcript_fetcher", transcript_fetcher)
    g.add_node("chunker_embedder", chunker_embedder)

    g.add_edge(START, "video_finder")
    g.add_edge("video_finder", "transcript_fetcher")
    g.add_edge("transcript_fetcher", "chunker_embedder")
    g.add_edge("chunker_embedder", END)

    # Summary and quiz generators are NOT in this graph — they run lazily on-demand
    # via dedicated endpoints so the user lands on the course page faster.
    return g


@lru_cache(maxsize=1)
def compiled_course_builder():
    """Sync-compiled graph (for scripts using .invoke())."""
    return _build_graph().compile(checkpointer=_checkpointer())


_async_graph = None


async def compiled_course_builder_async():
    """Async-compiled graph (for FastAPI endpoints using .astream()/.ainvoke())."""
    global _async_graph
    if _async_graph is None:
        saver = await _async_checkpointer()
        _async_graph = _build_graph().compile(checkpointer=saver)
    return _async_graph
