# CLAUDE.md — working rules for AI assistants in this repo

> **What this is:** AdaptivAI Mini — an agentic course generator. Type any tech topic; an agent assembles a mini-course (YouTube videos + transcripts + RAG tutor + lazy summary + quiz) in ~20s. See [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md) for the *why*, [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the *how*.

## Tech stack

Python 3.13 · **FastAPI** (async, SSE) · **LangGraph** (two `StateGraph`s, `AsyncSqliteSaver` in server path, `SqliteSaver` in scripts) · **LangChain** (Groq LLMs, HuggingFace embeddings, Chroma) · **LangSmith** (auto-tracing via env, `@traceable` on router) · vanilla HTML + Tailwind CDN frontend.

## How to run

```bash
cd C:\Users\Sheetal\Desktop\demo && .venv\Scripts\activate
python scripts/smoke_test.py "Docker basics"       # CLI sanity check
python -m uvicorn app:app --port 8000 --host 127.0.0.1
# http://127.0.0.1:8000  ·  API docs auto-generated at /docs
```

## File map

| Path | Purpose |
|---|---|
| `app.py` | FastAPI — 11 routes + SSE |
| `graphs/course_builder.py` | `video_finder → transcript_fetcher → chunker_embedder → END` |
| `graphs/tutor_chatbot.py` | `router → {retrieve_and_answer \| direct_answer \| clarify} → END` |
| `nodes/video.py` | YouTube search + transcript fetch |
| `nodes/indexing.py` | chunk + embed → Chroma |
| `nodes/generation.py` | `summary_generator`, `quiz_generator` + V1/V2 prompts |
| `nodes/chat.py` | `router` (`@traceable`), `retrieve_and_answer`, `direct_answer`, `clarify` |
| `models/schemas.py` | `CourseState`, `TutorState`, Pydantic outputs |
| `store/{catalog,chroma_client}.py` | SQLite catalog + per-course Chroma collections |
| `static/` | Vanilla HTML + `app.js` (sidebar shell, SSE helper, theming) |
| `evals/{dataset,evaluators}.py` | LangSmith dataset + LLM-as-judge |
| `scripts/{smoke_test,pregen_courses}.py` | CLI entry points |

## Agent architecture (the core)

**Two graphs, one Chroma collection per `course_id`. They do NOT share LangGraph state.**

| Graph | Cadence | Nodes | Why separate |
|---|---|---|---|
| Course Builder | once per topic, ~15-20s | `video_finder → transcript_fetcher → chunker_embedder` | Heavy, I/O-bound |
| Tutor Chatbot | per message, <2s | `router → {retrieve_and_answer \| direct_answer \| clarify}` | Hot path; conditional edge is the agentic money shot |

**Router decides between three routes**, never hardcoded:
- `needs_retrieval` — factual Q → RAG over Chroma with `[Video N]` citations
- `followup` — "thanks", "simpler please" → history-only answer (no retrieval)
- `unclear` — vague → clarifying template

Summary + quiz are **lazy** — generated on tab-click via `/api/courses/{id}/generate-{summary|quiz}`, NOT as part of the Course Builder graph.

## Coding conventions

- **State = `TypedDict`.** Access with `state["key"]`. Nodes return a dict of partial updates; never mutate input.
- **LCEL**: `prompt | llm.with_structured_output(Schema, method="json_mode")`. Always `json_mode` for Groq — function-calling mode fails on Llama with `tool_use_failed`.
- **Pydantic for typed outputs**: `Summary`, `Quiz`, `QuizQuestion`, `RouteDecision` in `models/schemas.py`. No `json.loads(msg.content)` anywhere.
- **Async vs sync**: `compiled_X_async()` for FastAPI endpoints, `compiled_X()` for scripts. Don't mix.
- **One Chroma collection per `course_id`** (`course_{course_id}`). Never pool.
- **`course_id` = LangGraph `thread_id`** — chat history persists per course.
- **SSE**: `event: <name>\ndata: <json>\n\n`. Events: `status`, `complete`, `error` (generation); `route`, `token`, `error`, `end` (chat).
- **Router stays `@traceable(name="router_decision")`** — it's the demo's money-shot span in LangSmith.

## Don't do

- Don't commit `.env`, `.sqlite*`, or `chroma_data/` (gitignored).
- Don't reintroduce `langchain-openai` — project moved to Groq + local HF embeddings.
- Don't merge the two graphs. They share Chroma, not state.
- Don't let the tutor answer without citations. Grounded-only is a load-bearing rule.
- Don't run upfront summary/quiz generation in the Course Builder graph — we explicitly moved them out to lazy endpoints for speed + cost.
- Don't remove `MAX_CHARS_PER_TRANSCRIPT` (default 6000) — it's what keeps us under Groq's 12k TPM free-tier cap.

## Failure modes → responses

| Symptom | Cause | Fix |
|---|---|---|
| Groq `400 tool_use_failed` | Llama emitted `<function=X>...` wrapper | Ensure every `with_structured_output` uses `method="json_mode"` |
| Groq `413 rate_limit_exceeded` (TPM) | Transcripts + prompt > 12k tokens | Lower `MAX_CHARS_PER_TRANSCRIPT` in `.env` |
| "Only 1 video with usable captions" | YouTube returned videos without captions | Retry or pick a common topic (Docker/React/Python/K8s/Git) |
| `NotImplementedError: SqliteSaver async` | Async path using sync saver | Endpoints must use `compiled_X_async()` |
| Router routes factual Q to `followup` | 8B classifier misreads | Add case to eval dataset; consider escalating router model |

## Before editing

- Graphs or nodes → read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) first.
- Endpoints → update the auto-generated `/docs` consumers; no hand-written API.md to keep in sync.
- Prompts → add/update an evaluator in `evals/evaluators.py`.
- Scope / direction → check [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Evals

```bash
python evals/dataset.py              # idempotent; creates 'adaptivai-mini-topics'
python evals/evaluators.py           # one experiment, current prompt
python evals/evaluators.py --both    # V1 vs V2 summary-prompt comparison
```
