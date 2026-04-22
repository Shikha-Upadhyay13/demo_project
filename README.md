# AdaptivAI Mini

**Type any tech topic. An AI agent builds you a mini-course in under a minute.**

Real YouTube videos + transcripts + RAG tutor with citations + lazy-generated summary + 5-question quiz. Two LangGraph state machines (Course Builder + Tutor Chatbot) behind a FastAPI backend and a vanilla HTML + Tailwind frontend.

> This is the MVP of **AdaptivAI** — a production-grade adaptive learning platform that combines Google Skills × NotebookLM with a real **learner model** to solve Bloom's 2-sigma problem at scale. See [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md).

## Quick start

```bash
# Windows
py -3.13 -m venv .venv && .venv\Scripts\activate

# macOS / Linux
python3.13 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env     # fill in GROQ_API_KEY, YOUTUBE_API_KEY, LANGSMITH_API_KEY

python scripts/smoke_test.py "Docker basics"              # CLI sanity check
python run.py                                              # start server (http://127.0.0.1:8000)
# API docs auto-generated at http://127.0.0.1:8000/docs

# If using Postgres backend (STORAGE_BACKEND=postgres), run the migration once first:
python scripts/pg_migrate.py
```

**Optional night-before**: `python scripts/pregen_courses.py` seeds 4 demo courses (Docker, React, Python, K8s).

**Evals**: `python evals/dataset.py` (create), `python evals/evaluators.py --both` (V1 vs V2 comparison).

## API keys

| Var | Where | Free tier |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | yes, generous |
| `YOUTUBE_API_KEY` | Google Cloud Console → YouTube Data API v3 | 10k units/day |
| `LANGSMITH_API_KEY` | https://smith.langchain.com | yes (optional — app runs without it; no traces) |

Also: `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=adaptivai-mini`.

## Troubleshooting

- **`pip install` fails** — use Python 3.13 via `py -3.13 -m venv .venv` (3.14 lacks some wheels).
- **Groq `400 tool_use_failed`** — shouldn't happen; if it does, check every `with_structured_output` uses `method="json_mode"`.
- **Groq `413 rate_limit`** — free-tier 12k TPM. Lower `MAX_CHARS_PER_TRANSCRIPT` in `.env` to `4000`.
- **"Only 1 video with usable captions"** — the topic has few captioned videos. Try something common (Docker, React, Python, Kubernetes, Git).
- **`NotImplementedError: SqliteSaver async`** — regression. Server must use `compiled_X_async()`, not `compiled_X()`.

## Architecture in one diagram

```
Course Builder (~15-20s, once per topic):
  START → video_finder → transcript_fetcher → chunker_embedder → END

Tutor Chatbot (per message, <2s):
  START → router ─┬─ retrieve_and_answer   (factual → RAG + [Video N] citations)
                  ├─ direct_answer         (follow-up → history only)
                  └─ clarify               (vague → ask back)
                                                        → END

Shared: one Chroma collection per course_id. No shared state.
```

## Tech stack (MVP)

Python 3.13 · **FastAPI** + uvicorn (SSE) · **LangGraph** (two `StateGraph`s) · **LangChain** (`ChatGroq`, `with_structured_output(method="json_mode")`, `HuggingFaceEmbeddings`, `Chroma`) · **LangSmith** (auto-tracing, `@traceable` router, LLM-as-judge evaluator) · **Groq** (Llama 3.3 70B + 3.1 8B) · **local HF embeddings** · **Chroma** + **SQLite** · vanilla HTML + Tailwind CDN.

## Docs

| File | For |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | AI assistant rules + agent architecture + coding conventions |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, graphs, schemas, SSE, invariants |
| [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md) | Why we're building this — Bloom 2σ, Learner DNA, adaptive engine |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 12-week phased plan |

## Where we're going

| Phase | Weeks | Focus |
|---|---|---|
| **0 — MVP** | shipped | Agentic primitives |
| **1 — Harden** | 1-4 | Postgres + pgvector + Clerk auth + Next.js + Fly.io + CI eval gate |
| **2 — Agentify** | 5-8 | `deepagents` refactor: 6 sub-agents (Research, Indexer, Tutor, Quizmaster, Coach, Assessor) |
| **3 — Learner DNA** | 9-12 | IRT + FSRS + mastery gates + spaced repetition + "you" tab |
| **4 — Launch** | 13-14 | Security, 50-learner pilot, billing, rollout |

Full plan: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## License

Internal. AdaptivAI / Genie AI Labs.
