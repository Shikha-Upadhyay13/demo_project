"""Tutor Chatbot nodes.

router is the agentic money shot — it CLASSIFIES before deciding what to do
rather than always retrieving. Decorated with @traceable so it shows up as a
named span in LangSmith (PRD §6.3).
"""
from __future__ import annotations

import logging
import os

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langsmith import traceable

from models.schemas import RouteDecision
from store.chroma_client import get_vector_store

log = logging.getLogger(__name__)

ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "llama-3.1-8b-instant")
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "llama-3.3-70b-versatile")
SMALL_MODEL = os.environ.get("SMALL_MODEL", "llama-3.1-8b-instant")

ROUTER_PROMPT = """Classify the user's latest message in a course chatbot.

Return one of three routes:

- needs_retrieval: a factual question whose answer depends on the course's video transcripts
  (e.g., "what's the difference between an image and a container?", "how does useEffect clean up?").
- followup: a short response, thanks, or a request to rephrase/simplify the previous assistant answer
  (e.g., "thanks", "say that simpler", "what do you mean?", "yes").
- unclear: too vague to answer without clarification (e.g., "how?", "why?", "explain", "tell me more"
  with no prior context).

Previous conversation (may be empty):
{history}

User message: {user_message}

Return ONLY a JSON object: {{"route": "needs_retrieval" | "followup" | "unclear"}}. No prose."""


RAG_PROMPT = """You are a tutor for a course on {topic_hint}. Answer the user's question using ONLY the
video transcript excerpts below. If the excerpts do not contain the answer, say so briefly.

When you state a fact, cite the source inline as [Video N] where N matches the Video number in the
excerpt headings. Multiple citations are fine. Do not invent video numbers.

Excerpts:
---
{context}
---

User question: {user_message}"""


FOLLOWUP_PROMPT = """You are a tutor continuing a short conversation. Use the conversation history to
understand what the user is referring to. Keep your answer conversational and brief — one or two
short paragraphs at most. Do not retrieve new material; just clarify or rephrase.

User message: {user_message}"""


CLARIFY_TEMPLATE = (
    "Could you say a bit more about what you're asking? "
    "For example, is there a specific concept, step, or video moment you'd like me to explain?"
)


def _format_history(messages: list) -> str:
    if not messages:
        return "(no prior turns)"
    lines: list[str] = []
    for m in messages[-6:]:  # last 3 pairs
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


@traceable(name="router_decision")
def router(state: dict) -> dict:
    """Classify the user message into one of three routes."""
    prompt = ChatPromptTemplate.from_template(ROUTER_PROMPT)
    llm = ChatGroq(model=ROUTER_MODEL, temperature=0)
    chain = prompt | llm.with_structured_output(RouteDecision, method="json_mode")

    history = _format_history(state.get("messages", []))
    decision: RouteDecision = chain.invoke(
        {"history": history, "user_message": state["user_message"]}
    )
    log.info("router: %r -> %s", state["user_message"][:80], decision.route)
    return {"route": decision.route}


def _build_context(chunks: list) -> tuple[str, list[str]]:
    """Render retrieved docs as labeled excerpts [Video N]; return context + raw chunks."""
    blocks: list[str] = []
    raw: list[str] = []
    for doc in chunks:
        v_idx = doc.metadata.get("video_idx", 0) + 1
        v_title = doc.metadata.get("video_title", "")
        blocks.append(f"[Video {v_idx}] ({v_title})\n{doc.page_content}")
        raw.append(doc.page_content)
    return "\n\n".join(blocks), raw


def retrieve_and_answer(state: dict) -> dict:
    """Pull top-k chunks and answer the question, grounded in transcripts."""
    vs = get_vector_store(state["course_id"])
    retriever = vs.as_retriever(search_kwargs={"k": 4})
    docs = retriever.invoke(state["user_message"])
    context, raw_chunks = _build_context(docs)

    topic_hint = ""  # not strictly needed for answer quality; chunks carry enough context
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT)
    llm = ChatGroq(model=ANSWER_MODEL, temperature=0.2)
    chain = prompt | llm

    result = chain.invoke(
        {"topic_hint": topic_hint, "context": context, "user_message": state["user_message"]}
    )
    answer = result.content if hasattr(result, "content") else str(result)
    log.info("retrieve_and_answer: %d chunks -> %d chars", len(docs), len(answer))

    return {
        "retrieved_chunks": raw_chunks,
        "answer": answer,
        "messages": [HumanMessage(content=state["user_message"]), AIMessage(content=answer)],
    }


def direct_answer(state: dict) -> dict:
    """Answer using chat history only. Skip retrieval."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful tutor. Keep replies short."),
            ("placeholder", "{history}"),
            ("human", FOLLOWUP_PROMPT),
        ]
    )
    llm = ChatGroq(model=SMALL_MODEL, temperature=0.4)
    chain = prompt | llm

    history = state.get("messages", [])[-6:]
    result = chain.invoke({"history": history, "user_message": state["user_message"]})
    answer = result.content if hasattr(result, "content") else str(result)
    log.info("direct_answer: produced %d chars", len(answer))
    return {
        "answer": answer,
        "messages": [HumanMessage(content=state["user_message"]), AIMessage(content=answer)],
    }


def clarify(state: dict) -> dict:
    """Return a clarifying question instead of answering."""
    log.info("clarify: returning template question")
    return {
        "answer": CLARIFY_TEMPLATE,
        "messages": [
            HumanMessage(content=state["user_message"]),
            AIMessage(content=CLARIFY_TEMPLATE),
        ],
    }
