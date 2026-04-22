# Roadmap

> **Status**: Phase 0 (MVP) shipped. We have two graphs, RAG tutor with citations, lazy summary/quiz, Groq + local HF embeddings + Chroma, SQLite catalog + checkpoints, LangSmith auto-tracing + one LLM-as-judge evaluator, demo-level auth + bookmarks + my-courses.

## 12-week plan

| Phase | Weeks | Goal |
|---|---|---|
| **0 — MVP** | shipped | Prove agentic primitives |
| **1 — Harden** | 1-4 | Production-shaped without changing agent behavior |
| **2 — Agentify** | 5-8 | True multi-agent via `deepagents` |
| **3 — Learner DNA** | 9-12 | Adaptive engine — the moat |
| **4 — Launch** | 13-14 | Pilot, security, billing, rollout |

## Phase 1 — Harden (weeks 1-4)

| Area | What ships |
|---|---|
| **Persistence** | Postgres + pgvector (one DB). `AsyncPostgresSaver` checkpointer. Migration scripts off SQLite + Chroma |
| **Auth** | Clerk OAuth + FastAPI JWT middleware. Every `/api/*` route scoped by `user_id` |
| **Frontend** | Next.js 15 (App Router, RSC, streaming) in `frontend/`. Keeps current visual identity |
| **Deploy** | Docker + Fly.io (or Railway). Secrets via Doppler |
| **Observability** | Sentry + CI eval gate via GitHub Actions. Two new evaluators: groundedness + router accuracy |

**Files changed**: `requirements.txt` (+`langgraph-checkpoint-postgres`, `+langchain-postgres`; −Chroma), `graphs/*.py` (swap saver), `store/chroma_client.py` → `store/pgvector.py`, `store/catalog.py` (Postgres), `app.py` (auth middleware), new `Dockerfile` + `fly.toml` + `.github/workflows/eval-gate.yml`.

## Phase 2 — Agentify (weeks 5-8)

Refactor to `langchain-ai/deepagents`. Orchestrator + 6 sub-agents, each with own eval dataset.

| Sub-agent | Purpose |
|---|---|
| 🔍 ResearchAgent | Sources from YouTube + web + docs |
| 📖 IndexerAgent | Chunk + embed into pgvector |
| 🧠 TutorAgent | RAG Q&A with citations |
| 📝 QuizmasterAgent | Generate + grade (IRT-ready) |
| 🎯 CoachAgent | Detect struggle, re-teach |
| 🪞 AssessorAgent | Update mastery estimates |

**Pattern**: Supervisor, not Swarm — deterministic, per-user auditable.
**New files**: `agents/orchestrator.py`, `agents/*_agent.py`, `agents/tools.py`, per-agent evals in `evals/`.

## Phase 3 — Learner DNA (weeks 9-12)

**The moat.** Make the tutor adapt to *this* learner.

| Piece | Ship |
|---|---|
| Schema | `learner_dna`, `attempts`, `review_schedule` (Postgres) |
| Adaptive quiz | `engine/irt.py` — IRT item selection with time-sensitive θ updates |
| Spaced review | `engine/fsrs.py` — FSRS algorithm |
| Struggle detection | CoachAgent triggers on response-time outliers / consecutive wrong |
| Mastery gates | AssessorAgent blocks skill progression until θ ≥ threshold |
| UI | "You" tab — DNA dashboard, mastery constellation, editable preferences |
| Onboarding | 3-minute diagnostic sets initial θ + modality prefs |
| Transfer eval | Novel-scenario questions, not repeated practice |

Signals ingested: accuracy · response_ms · attempts · modality engagement · confidence calibration · transfer success.

## Phase 4 — Launch (weeks 13-14)

- **Load tests**: 1k concurrent generations, 10k concurrent chats (k6 / locust)
- **Security**: OWASP top 10 + prompt injection review + PII scrub on traces
- **Pilot**: 50 learners across 3 personas, 4-week usage, mastery lift vs control
- **Billing**: Stripe free (10 gens/day) + pro (unlimited)
- **Rollout**: Waitlist → gradual via GrowthBook

## Success metrics (launch exit criteria)

| Metric | Target |
|---|---|
| Mastery lift | +1σ pre/post |
| Session completion | >70% |
| Calibration accuracy (θ vs external) | ≥0.8 |
| Transfer rate on novel scenarios | >60% |
| Time-to-skill vs non-adaptive | −30 to −40% |
| Router accuracy | ≥92% |
| Groundedness | ≥95% |
| Day-30 retention | >35% |

## Risks

| Risk | Mitigation |
|---|---|
| IRT cold-start (not enough attempts) | Seed with LLM-as-judge calibration; pool across similar learners early |
| Hallucinated tutor answers | Groundedness eval gate in CI; citation-required prompts |
| Agent cost blowouts | Model cascade (8B → 70B → frontier) + Redis prompt cache + per-user caps |
| YouTube quota / ToS | Dual-source (YT + web docs) by Phase 2 |
| Learner DNA = privacy risk | Data minimization, encrypted-at-rest, user-editable "you" tab |
| Multi-tenant state leakage | Row-level security + per-user `thread_id` + isolation tests |

## Not in scope (yet)

Mobile native app · on-device inference · peer cohorts / social · video generation · real-time voice tutoring.
