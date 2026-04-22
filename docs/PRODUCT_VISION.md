# Product Vision — AdaptivAI

*A personalized, agentic learning platform. Google Skills × NotebookLM × Bloom's 2-sigma.*

## Why this exists

For decades, learning has been one-size-fits-all. A tutor with 100 students can't meet each at their level. Bloom (1984) showed that **1:1 tutoring outperforms classroom learning by ~2σ** — the "2-sigma problem." The reason tutoring works: real-time formative feedback, adaptive pacing, emphasis on specific gaps. We've never been able to scale that — until now.

The MVP in this repo proves the agentic primitives work. The missing piece is a **learner model**: a running picture of what *this specific person* knows, how they learn, and what they need next. That's the moat.

## One-sentence vision

**AdaptivAI is an adaptive learning platform where an AI agent builds you a personalized course on any topic — then tutors, tests, and re-teaches you until you've genuinely mastered it, adjusting to the way *you* learn.**

## Personas

| Who | Broken today | What AdaptivAI does |
|---|---|---|
| **Arjun, 19, self-taught dev** | Docker tutorials assume too much / too little | 3-min diagnostic places him; scales difficulty as he proves mastery |
| **Priya, 34, pivoting to tech sales** | Needs SaaS + tech fundamentals in 3 weeks | Generates path with SaaS basics + MEDDIC + 10 role-play sims |
| **Karim, 12, dyslexic** | Text-heavy courses fail him | Detects modality; defaults to audio + mind maps + voice-first chat |
| **Dr. Lee, 45, pediatrician** | Needs specific stats gaps, not a full course | Diagnoses sub-skills; teaches in her domain's examples |
| **Reskilling team, 200 employees** | K8s training from different starting points | One seed curriculum → personalized path per employee; admin dashboard |

## Scenarios

**Docker from scratch.** Arjun signs up → diagnostic → personalized path → Audio Overview on commute → lesson workspace → 5-question adaptive quiz → gets Q3 wrong → tutor explains *why* with the specific video snippet → spaced review card slotted for 2 days later. 3 weeks later: 72% transfer on novel scenarios.

**Struggling moment.** Dr. Lee's response times climb 20s → 90s. Time-sensitive IRT flags hesitation. CoachAgent asks what's confusing. She admits she's shaky on "effect size." Coach pulls a focused explainer, 3 worked examples, re-asks. She gets it. The system updates her mastery estimate **and notes response latency is a strong signal for her specifically**.

## How we beat Google Skills + NotebookLM

| Capability | Google Skills | NotebookLM | AdaptivAI |
|---|:-:|:-:|:-:|
| Ready-made catalog | ✅ 450+ | ❌ | ✅ Infinity (agent-generated) |
| Multi-modal study surfaces | ❌ | ✅ | ✅ |
| **Learner model** | ❌ | ❌ | ✅ **(moat)** |
| Real-time formative feedback | ❌ | ❌ | ✅ |
| Adaptive difficulty (IRT/ZPD) | ❌ | ❌ | ✅ Phase 3 |
| Mastery gates | ❌ | ❌ | ✅ Phase 3 |
| Spaced repetition | ❌ | ❌ | ✅ Phase 3 |
| Transfer testing | ❌ | ❌ | ✅ Phase 3 |
| Grounded in real sources | ❌ | ✅ | ✅ |

**Short form**: NotebookLM is a notebook — passive. Google Skills is a catalog — static. AdaptivAI is a tutor — active, adaptive, personal.

## Learner DNA (the moat)

```sql
learner_dna      (user_id, modality_prefs JSONB, focus_window_mins, pace,
                  bloom_ability JSONB, confusion_signals JSONB, goals JSONB, updated_at)
attempts         (user_id, skill_id, item_id, correct, response_ms,
                  confidence_pct, attempt_n, created_at)
review_schedule  (user_id, card_id, due_at, ease_factor, interval_days)  -- FSRS
```

Signals ingested: accuracy, response time (hesitation), attempts-to-mastery (persistence), modality engagement, confidence calibration, transfer success.

Writes from: `AssessorAgent` (every attempt) · `CoachAgent` (re-teach moments) · client telemetry (modality engagement).

## Adaptive engine — the science

| Mechanism | Effect d | Where |
|---|:-:|---|
| Retrieval practice | 0.74 | 3-card flash end of every lesson + spaced reviews |
| Formative feedback | 0.73 | `CoachAgent` on every wrong answer |
| Spaced repetition (FSRS) | 0.55 | `review_schedule` scheduler |
| Zone of Proximal Dev | 0.50 | IRT item selection targets P(correct) ≈ 0.7 |
| Mastery learning | 0.50 | `AssessorAgent` gates progression |
| Interleaving | 0.44 | Review sessions mix skills |

**Time-sensitive IRT** (2025 research): response latency feeds θ updates — slow correct answers update θ less. Distinguishes "knows it" from "guessed right."

## Success metrics

| Metric | Target | Why |
|---|---|---|
| Mastery lift | +1σ pre/post | The actual learning-science goal |
| Transfer rate | >60% novel-scenario | Learning vs memorization |
| Calibration | ≥0.8 θ vs external | Are we right about what they know? |
| Time-to-skill | −30 to −40% | Productivity win |
| Groundedness | ≥95% traceable | Trust |
| Day-30 retention | >35% | Pull |

## Compass (use this when any feature comes up)

1. **The learner model is the product.** Not content. Not UI. Content and UI are commodities.
2. **Groundedness beats quantity.** Tutor cites sources or says "I don't know." Never trade truth for surface area.
3. **Evidence-based pedagogy, not cargo-cult gamification.** Streaks and XP don't move mastery. IRT + spaced repetition + retrieval practice do.
4. **Trust is a feature.** User-editable Learner DNA ("you" tab) is a moat, not a settings page.
5. **Productive friction.** The system pushes learners to the edge of their ZPD, not coddles them.
