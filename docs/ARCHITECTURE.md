# Architecture

## System at a glance

```
┌─────────────┐       SSE        ┌───────────────────────────┐
│   Browser   │ ◄════════════════│  FastAPI (uvicorn)        │
│  static/    │   POST JSON      │  app.py — 11 routes       │
└─────────────┘ ────────────────►│  ┌─────────────────────┐  │
                                 │  │  LangGraph async    │  │
                                 │  │   CourseBuilder     │  │
                                 │  │   TutorChatbot      │  │
                                 │  └─────────────────────┘  │
                                 └──┬───────────┬─────────┬──┘
                                    │           │         │
                              ┌─────▼───┐  ┌────▼────┐ ┌──▼─────┐
                              │  Groq   │  │ Chroma  │ │SQLite  │
                              │ Llama   │  │ 1 col/  │ │catalog │
                              │ 70B+8B  │  │course_id│ │+ ckpts │
                              └─────────┘  └──▲──────┘ └────────┘
                                              │
                                        ┌─────┴──────┐   ┌───────────────┐
                                        │ HF local   │   │ LangSmith     │
                                        │ embeddings │   │ auto-trace    │
                                        └────────────┘   │ + @traceable  │
                                                         │ router span   │
                                                         └───────────────┘
```

## Two graphs

**Both compile twice**: sync (`compiled_X()`) for scripts, async (`compiled_X_async()`) for FastAPI. Checkpointer: `SqliteSaver` / `AsyncSqliteSaver` backed by the same `checkpoints.sqlite`. Thread ID = `course_id`.

### Course Builder — `graphs/course_builder.py`

Runs once per new topic, ~15-20s, heavy I/O.

```
START → video_finder → transcript_fetcher → chunker_embedder → END
```

| Node | Writes to state | Side effect |
|---|---|---|
| `video_finder` | `videos` (up to 5) | YouTube Data API v3 search (tutorials, English, medium duration) |
| `transcript_fetcher` | `videos` (filtered), `transcripts` | `youtube-transcript-api`; drops captionless; `ValueError` if <2 usable |
| `chunker_embedder` | `vector_collection_name` | `RecursiveCharacterTextSplitter(1000/200)` → `HuggingFaceEmbeddings` → Chroma add with `{video_idx, video_id, video_title}` metadata |

State: `CourseState` in `models/schemas.py`. `summary` and `quiz` are populated later by lazy endpoints, not by this graph.

### Tutor Chatbot — `graphs/tutor_chatbot.py`

Runs per chat message, <2s, the **conditional edge** is the agentic centerpiece.

```
START → router ─┬─ retrieve_and_answer     (factual → RAG + [Video N] citations)
                ├─ direct_answer           (follow-up → history only)
                └─ clarify                 (vague → ask back)
                                                    → END
```

| Node | LLM | Notes |
|---|---|---|
| `router` | `llama-3.1-8b-instant` | `@traceable(name="router_decision")` · `with_structured_output(RouteDecision, method="json_mode")` |
| `retrieve_and_answer` | `llama-3.3-70b-versatile` | `Chroma.as_retriever(k=4)`; context labeled `[Video N] (title)\n...`; instructed to cite |
| `direct_answer` | `llama-3.1-8b-instant` | Uses last 6 messages; no retrieval |
| `clarify` | — | Fixed template response |

State: `TutorState`. Falls through to `clarify` on any unknown route label.

## Why two graphs, not one

- **Rates differ**: Course Builder runs once per topic, Tutor Chatbot runs many times per topic.
- Merging would put the hot chat path behind heavy course-builder state.
- They share data through **Chroma by `course_id`**, not through LangGraph state.

## Lazy summary + quiz

Moved out of the Course Builder graph to cut user-facing latency and token cost.

- `POST /api/courses/{id}/generate-summary` → calls `summary_generator({topic, transcripts})` directly, persists to `catalog.payload.summary`.
- `POST /api/courses/{id}/generate-quiz` → same pattern with `quiz_generator`.
- Frontend checks cache on tab-click; generates on demand if empty.

## State schemas (`models/schemas.py`)

```python
class CourseState(TypedDict, total=False):
    course_id: str
    topic: str
    videos: list[dict]                # {id, title, channel, url, thumbnail}
    transcripts: list[str]
    vector_collection_name: str
    summary: str                      # populated by lazy endpoint
    quiz: list[dict]                  # populated by lazy endpoint
    messages: Annotated[list, add_messages]

class TutorState(TypedDict, total=False):
    course_id: str
    user_message: str
    route: str                        # needs_retrieval | followup | unclear
    retrieved_chunks: list[str]
    answer: str
    messages: Annotated[list, add_messages]

# Typed outputs:
# Summary(markdown), Quiz(questions[5]), QuizQuestion(q/options[4]/correct_idx/explanation),
# RouteDecision(route: Literal[...])
```

## SSE streaming

Wire format: `event: <name>\ndata: <json>\n\n`. Client uses `fetch` + `ReadableStream` (not `EventSource` — we need POST).

| Endpoint | Events |
|---|---|
| `POST /api/courses/generate` | `status {node, message}` per completed node · `complete {course_id}` · `error {message}` |
| `POST /api/courses/{id}/chat` | `route {route}` once · `token {text}` per LLM chunk · `end {}` · `error {message}` |

Helpers: `_sse()` in `app.py`, `streamSSE()` in `static/app.js`.

## Endpoints

**Full spec**: run the app and open `http://127.0.0.1:8000/docs` (FastAPI auto-generates OpenAPI + Swagger UI).

Summary:

| Method | Path | Purpose |
|---|---|---|
| GET | `/` `/login` `/catalog` `/my-courses` `/bookmarks` `/course/{id}` | HTML pages |
| GET | `/api/catalog` | List all courses |
| POST | `/api/courses/generate` (SSE) · `/generate-sync` | Run Course Builder |
| GET | `/api/courses/{id}` | Full payload |
| POST | `/api/courses/{id}/generate-summary` · `/generate-quiz` | Lazy generation |
| POST | `/api/courses/{id}/chat` (SSE) | Run Tutor Chatbot |
| POST | `/api/courses/{id}/quiz/grade` | Score submitted answers |

## Persistence

| Store | File / dir | What |
|---|---|---|
| Catalog | `catalog.sqlite` | `courses(course_id, topic, video_count, created_at, payload JSON)` |
| Checkpoints | `checkpoints.sqlite` (+ `-shm`, `-wal`) | LangGraph state per `thread_id` |
| Vectors | `chroma_data/` | One collection per course (`course_{course_id}`) |

All three converge on **Postgres + pgvector** in Phase 1 (see ROADMAP).

## Frontend

Vanilla HTML + Tailwind CDN + one `app.js` + marked.js. No build step. `app.js` injects a shared sidebar + topbar into `#sidebar-slot` / `#topbar-slot` on every page. Per-topic theming via `themeFor(topic)` (emoji + gradient from stable hash). User state + bookmarks + owned courses in `localStorage` (demo only; Phase 1 swaps in real auth).

## Design invariants (don't break)

1. Two graphs, one Chroma collection per `course_id`. Never merge state across graphs.
2. Every structured output uses `method="json_mode"` (Groq + Llama function-calling is unreliable).
3. `MAX_CHARS_PER_TRANSCRIPT` (default 6000) keeps us under Groq's 12k TPM free-tier cap.
4. Sync → `SqliteSaver`, async → `AsyncSqliteSaver`. Two compiled graphs per module.
5. `@traceable(name="router_decision")` on `router` — the demo's money-shot LangSmith span.
6. Tutor cites `[Video N]` or says "I don't know." No ungrounded answers.
