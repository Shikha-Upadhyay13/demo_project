"""Course Builder graph — runs once per new topic.

Linear up to the embedder, then fans out in parallel to summary + quiz.
Parallel branching is a real deliverable (PRD §3.1) — two add_edge calls
from the same source are how LangGraph concurrency is expressed.
"""
from __future__ import annotations

import os
import sqlite3
from functools import lru_cache

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from models.schemas import CourseState
from nodes.indexing import chunker_embedder
from nodes.video import transcript_fetcher, video_finder

CHECKPOINT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints.sqlite"))


@lru_cache(maxsize=1)
def _checkpointer() -> SqliteSaver:
    # check_same_thread=False so FastAPI worker threads can share the connection.
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    return SqliteSaver(conn)


_async_saver: AsyncSqliteSaver | None = None


async def _async_checkpointer() -> AsyncSqliteSaver:
    """Lazy-init the async checkpointer. Must be awaited inside an async context."""
    global _async_saver
    if _async_saver is None:
        conn = await aiosqlite.connect(CHECKPOINT_DB, check_same_thread=False)
        _async_saver = AsyncSqliteSaver(conn)
    return _async_saver


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
    """Sync-compiled graph (for scripts that use .invoke())."""
    return _build_graph().compile(checkpointer=_checkpointer())


_async_graph = None


async def compiled_course_builder_async():
    """Async-compiled graph (for FastAPI endpoints that use .astream()/.ainvoke())."""
    global _async_graph
    if _async_graph is None:
        saver = await _async_checkpointer()
        _async_graph = _build_graph().compile(checkpointer=saver)
    return _async_graph
