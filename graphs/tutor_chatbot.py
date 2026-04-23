"""Tutor Chatbot graph.

One START → router → {retrieve_and_answer | direct_answer | clarify} → END.

The conditional edge is the most agentic concept in the demo: most RAG
chatbots retrieve every turn; this one decides.
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from graphs.course_builder import _async_checkpointer, _checkpointer
from models.schemas import TutorState
from nodes.chat import clarify, direct_answer, greet, retrieve_and_answer, router


def _route_selector(state: dict) -> str:
    # Fallback to clarify on anything unexpected from the LLM classifier.
    route = state.get("route", "unclear")
    return route if route in {"needs_retrieval", "followup", "unclear", "greeting"} else "unclear"


def _build_graph() -> StateGraph:
    g = StateGraph(TutorState)

    g.add_node("router", router)
    g.add_node("retrieve_and_answer", retrieve_and_answer)
    g.add_node("direct_answer", direct_answer)
    g.add_node("clarify", clarify)
    g.add_node("greet", greet)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        _route_selector,
        {
            "needs_retrieval": "retrieve_and_answer",
            "followup": "direct_answer",
            "unclear": "clarify",
            "greeting": "greet",
        },
    )
    g.add_edge("retrieve_and_answer", END)
    g.add_edge("direct_answer", END)
    g.add_edge("clarify", END)
    g.add_edge("greet", END)
    return g


@lru_cache(maxsize=1)
def compiled_tutor_chatbot():
    """Sync-compiled chatbot (for scripts)."""
    return _build_graph().compile(checkpointer=_checkpointer())


_async_chatbot = None


async def compiled_tutor_chatbot_async():
    """Async-compiled chatbot (for FastAPI endpoints)."""
    global _async_chatbot
    if _async_chatbot is None:
        saver = await _async_checkpointer()
        _async_chatbot = _build_graph().compile(checkpointer=saver)
    return _async_chatbot
