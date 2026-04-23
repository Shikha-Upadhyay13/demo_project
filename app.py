"""FastAPI app — 7 endpoints from PRD §5, plus a /generate-sync backup.

The two streaming endpoints are the core agentic surface:
  - /api/courses/generate  streams node-level progress events while the
    Course Builder graph runs, so the UI can render the agent's steps.
  - /api/courses/{id}/chat  streams tokens from the Tutor Chatbot graph.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

# psycopg async requires SelectorEventLoop on Windows; ProactorEventLoop (uvicorn default) fails.
# Must set BEFORE uvicorn creates the loop — i.e. at module import time.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from langchain_core.messages import AIMessageChunk

from graphs.course_builder import compiled_course_builder_async
from graphs.tutor_chatbot import compiled_tutor_chatbot_async
from store import catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("adaptivai-mini")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AdaptivAI Mini", docs_url="/docs")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def _warm_embeddings() -> None:
    """Preload HuggingFace embeddings + tokenize once so the first chat is
    fast. Without this, the first retrieval pays a ~20s hit to download
    config files from HF Hub (unauthenticated → rate-limited) and load
    BertModel weights."""
    def _warmup() -> None:
        try:
            from store.chroma_client import get_vector_store

            # Arbitrary course_id — creating the Chroma/PGVector wrapper triggers
            # HuggingFaceEmbeddings instantiation (which is @lru_cached), which
            # loads the model + downloads any missing config files.
            vs = get_vector_store("__warmup__")
            # Force the embedding pipeline to run once so the tokenizer + model
            # weights are actually resident in memory.
            vs.embeddings.embed_query("warmup")
            log.info("embeddings warm-up complete")
        except Exception as e:
            log.warning("embeddings warm-up skipped: %s", e)

    await asyncio.to_thread(_warmup)


# ---------- Page routes ----------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/catalog")
def catalog_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "catalog.html")


@app.get("/my-courses")
def my_courses_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "my-courses.html")


@app.get("/bookmarks")
def bookmarks_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "bookmarks.html")


@app.get("/course/{course_id}")
def course_page(course_id: str) -> FileResponse:
    # The HTML is static; app.js reads the id from the URL and hydrates.
    return FileResponse(STATIC_DIR / "course.html")


# ---------- SSE helper ----------

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------- Status messages keyed by node ----------

NODE_STATUS: dict[str, str] = {
    "video_finder": "Searching for the best videos...",
    "transcript_fetcher": "Fetching transcripts...",
    "chunker_embedder": "Indexing knowledge...",
}


# ---------- Catalog ----------

@app.get("/api/catalog")
def get_catalog() -> JSONResponse:
    return JSONResponse(catalog.list_all())


# ---------- Generation (SSE) ----------

async def _generate_stream(topic: str):
    course_id = f"crs_{uuid.uuid4().hex[:10]}"
    config = {"configurable": {"thread_id": course_id}}
    graph = await compiled_course_builder_async()

    yield _sse("status", {"node": "start", "message": f"Starting for {topic!r}..."})

    final_state: dict = {"course_id": course_id, "topic": topic}
    try:
        # stream_mode="updates" yields {node_name: node_output_dict} per step.
        async for event in graph.astream(
            {"course_id": course_id, "topic": topic},
            config=config,
            stream_mode="updates",
        ):
            for node_name, partial in event.items():
                if node_name in NODE_STATUS:
                    yield _sse("status", {"node": node_name, "message": NODE_STATUS[node_name]})
                if isinstance(partial, dict):
                    final_state.update(partial)
    except ValueError as e:
        log.warning("generation failed: %s", e)
        yield _sse("error", {"message": str(e)})
        return
    except Exception as e:
        log.exception("generation crashed")
        yield _sse("error", {"message": f"Unexpected error: {e.__class__.__name__}"})
        return

    payload = {
        "videos": final_state.get("videos", []),
        "transcripts": final_state.get("transcripts", []),
        "summary": final_state.get("summary", ""),
        "quiz": final_state.get("quiz", []),
    }
    catalog.upsert(course_id=course_id, topic=topic, payload=payload)

    yield _sse("complete", {"course_id": course_id})


@app.post("/api/courses/generate")
async def generate(request: Request) -> StreamingResponse:
    body = await request.json()
    topic = (body or {}).get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    return StreamingResponse(
        _generate_stream(topic),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/courses/generate-sync")
async def generate_sync(request: Request) -> JSONResponse:
    """Non-streaming fallback (PRD §12 risk mitigation)."""
    body = await request.json()
    topic = (body or {}).get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")

    course_id = f"crs_{uuid.uuid4().hex[:10]}"
    config = {"configurable": {"thread_id": course_id}}
    graph = await compiled_course_builder_async()

    try:
        final = await graph.ainvoke({"course_id": course_id, "topic": topic}, config=config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    payload = {
        "videos": final.get("videos", []),
        "transcripts": final.get("transcripts", []),
        "summary": final.get("summary", ""),
        "quiz": final.get("quiz", []),
    }
    catalog.upsert(course_id=course_id, topic=topic, payload=payload)
    return JSONResponse({"course_id": course_id})


# ---------- Course detail ----------

@app.get("/api/courses/{course_id}")
def get_course(course_id: str) -> JSONResponse:
    row = catalog.get(course_id)
    if not row:
        raise HTTPException(status_code=404, detail="course not found")
    out = {
        "course_id": row["course_id"],
        "topic": row["topic"],
        "created_at": row["created_at"],
        **row["payload"],
    }
    return JSONResponse(out)


# ---------- Lazy summary + quiz generation ----------

def _lazy_generate(course_id: str, kind: str) -> dict:
    """Run summary or quiz generator on-demand, cache to catalog, return payload.

    kind: 'summary' | 'quiz'
    """
    from nodes.generation import quiz_generator, summary_generator

    row = catalog.get(course_id)
    if not row:
        raise HTTPException(status_code=404, detail="course not found")
    payload = row["payload"]

    # Return cached if present.
    if kind == "summary" and payload.get("summary"):
        return {"summary": payload["summary"]}
    if kind == "quiz" and payload.get("quiz"):
        return {"quiz": payload["quiz"]}

    transcripts = payload.get("transcripts", [])
    if not transcripts:
        raise HTTPException(status_code=409, detail="course has no transcripts yet")

    state = {"topic": row["topic"], "transcripts": transcripts}
    try:
        if kind == "summary":
            out = summary_generator(state)
            payload["summary"] = out["summary"]
        else:
            out = quiz_generator(state)
            payload["quiz"] = out["quiz"]
    except Exception as e:
        log.exception("%s generation failed", kind)
        raise HTTPException(status_code=502, detail=f"{kind} generation failed: {e.__class__.__name__}")

    catalog.upsert(course_id=course_id, topic=row["topic"], payload=payload)
    return out


@app.post("/api/courses/{course_id}/generate-summary")
async def generate_summary(course_id: str) -> JSONResponse:
    return JSONResponse(_lazy_generate(course_id, "summary"))


@app.post("/api/courses/{course_id}/generate-quiz")
async def generate_quiz(course_id: str) -> JSONResponse:
    return JSONResponse(_lazy_generate(course_id, "quiz"))


# ---------- Chat (SSE tokens) ----------

async def _chat_stream(course_id: str, message: str):
    graph = await compiled_tutor_chatbot_async()
    config = {"configurable": {"thread_id": course_id}}

    # Stream messages (tokens) from the graph. We use the "messages" mode so
    # we get LLM tokens as they arrive.
    sent_route = False
    collected_answer_parts: list[str] = []

    try:
        async for mode, chunk in graph.astream(
            {"course_id": course_id, "user_message": message},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            if mode == "updates":
                for node_name, partial in chunk.items():
                    if node_name == "router" and not sent_route:
                        sent_route = True
                        yield _sse("route", {"route": partial.get("route", "unclear")})
                    # clarify + greet are synchronous (no LLM stream). Emit their answer as one token.
                    if node_name in {"clarify", "greet"}:
                        final = partial.get("answer", "")
                        if final:
                            yield _sse("token", {"text": final})
            elif mode == "messages":
                msg, meta = chunk
                node = meta.get("langgraph_node")
                # Only emit genuine streaming chunks (AIMessageChunk). Full
                # AIMessage/HumanMessage appended to state at node return are
                # also routed through this channel — skip them or the reply
                # gets echoed twice.
                if (
                    node in {"retrieve_and_answer", "direct_answer"}
                    and isinstance(msg, AIMessageChunk)
                    and getattr(msg, "content", "")
                ):
                    piece = msg.content
                    collected_answer_parts.append(piece)
                    yield _sse("token", {"text": piece})
    except Exception as e:
        log.exception("chat stream crashed")
        yield _sse("error", {"message": f"Chat error: {e.__class__.__name__}"})
        return

    yield _sse("end", {})


@app.post("/api/courses/{course_id}/chat")
async def chat(course_id: str, request: Request) -> StreamingResponse:
    body = await request.json()
    message = (body or {}).get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if not catalog.get(course_id):
        raise HTTPException(status_code=404, detail="course not found")
    return StreamingResponse(
        _chat_stream(course_id, message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Quiz grading ----------

@app.post("/api/courses/{course_id}/quiz/grade")
async def grade_quiz(course_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    answers: list[int] = (body or {}).get("answers", [])
    row = catalog.get(course_id)
    if not row:
        raise HTTPException(status_code=404, detail="course not found")

    quiz = row["payload"].get("quiz", [])
    if len(answers) != len(quiz):
        raise HTTPException(
            status_code=400,
            detail=f"expected {len(quiz)} answers, got {len(answers)}",
        )

    feedback = []
    correct = 0
    for q, a in zip(quiz, answers):
        is_right = int(a) == int(q["correct_idx"])
        if is_right:
            correct += 1
        feedback.append(
            {
                "correct": is_right,
                "correct_idx": q["correct_idx"],
                "explanation": q["explanation"],
            }
        )

    return JSONResponse({"score": correct, "total": len(quiz), "feedback": feedback})
