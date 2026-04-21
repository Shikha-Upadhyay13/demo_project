"""Summary + quiz generation nodes (parallel branch of the Course Builder)."""
from __future__ import annotations

import logging
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from models.schemas import Quiz, Summary

log = logging.getLogger(__name__)


# Keep two prompt versions for the LangSmith v1-vs-v2 experiment (PRD §6.3).
SUMMARY_PROMPT_V1 = """You are a technical writer. Summarize the material below for a learner new to {topic}.

Material (video transcripts joined):
---
{material}
---

Write a concise markdown summary covering key concepts and any important examples."""

SUMMARY_PROMPT_V2 = """You are a senior engineer writing a course brief for someone new to {topic}.

Using only the material below (joined YouTube transcripts), write a markdown summary with:

1. A one-paragraph **Overview** — what this topic is and why it matters.
2. **Key Concepts** — bulleted list, 4-7 items. Each bullet names the concept in bold and explains it in one sentence.
3. **Code or Commands** (if the transcripts show any) — fenced code blocks with a one-line caption above.
4. **Next Steps** — 3 concrete things the learner should try after watching.

Rules: do not invent facts not in the material. Do not mention the videos or channels by name. Use markdown headings (`##`).

Material:
---
{material}
---"""

# Which version is live today. Swap the constant + rerun the evaluator to produce the experiment.
ACTIVE_SUMMARY_PROMPT = SUMMARY_PROMPT_V2


QUIZ_PROMPT = """You are writing a 5-question multiple choice quiz for a learner studying {topic}.

Source material (joined YouTube transcripts):
---
{material}
---

Rules:
- Exactly 5 questions.
- Each question has exactly 4 options.
- correct_idx is the 0-based index of the correct option.
- Avoid trivia and definitions-only questions. Favor questions that test understanding of behavior, tradeoffs, or when to use a concept.
- Mix difficulty: 2 beginner, 2 intermediate, 1 harder.
- Every explanation should be 1-3 sentences and reference the concept, not the letter.
- Do not reference the videos or the material directly."""


def _llm(model: str | None = None, temperature: float = 0.2) -> ChatGroq:
    return ChatGroq(
        model=model or os.environ.get("GENERATION_MODEL", "llama-3.3-70b-versatile"),
        temperature=temperature,
    )


def _joined_material(transcripts: list[str]) -> str:
    # Label each transcript so the model can implicitly attribute material.
    blocks = [f"[Video {i+1}]\n{t}" for i, t in enumerate(transcripts)]
    return "\n\n".join(blocks)


def summary_generator(state: dict) -> dict:
    prompt = ChatPromptTemplate.from_template(
        ACTIVE_SUMMARY_PROMPT
        + '\n\nReturn ONLY a JSON object matching this schema: {{"markdown": "<the full markdown string>"}}'
    )
    # json_mode is more reliable than function_calling for Llama on Groq.
    chain = prompt | _llm(temperature=0.2).with_structured_output(Summary, method="json_mode")

    result: Summary = chain.invoke(
        {"topic": state["topic"], "material": _joined_material(state["transcripts"])}
    )
    log.info("summary_generator: produced %d chars", len(result.markdown))
    return {"summary": result.markdown}


def quiz_generator(state: dict) -> dict:
    prompt = ChatPromptTemplate.from_template(
        QUIZ_PROMPT
        + '\n\nReturn ONLY a JSON object matching this schema:\n'
        + '{{"questions": [\n'
        + '  {{"q": "<question>", "options": ["<a>", "<b>", "<c>", "<d>"], "correct_idx": 0, "explanation": "<why>"}},\n'
        + '  ... (exactly 5 items total)\n'
        + ']}}\n'
        + 'No prose, no code fences, just the JSON object.'
    )
    chain = prompt | _llm(temperature=0).with_structured_output(Quiz, method="json_mode")

    result: Quiz = chain.invoke(
        {"topic": state["topic"], "material": _joined_material(state["transcripts"])}
    )
    quiz = [q.model_dump() for q in result.questions]
    log.info("quiz_generator: produced %d questions", len(quiz))
    return {"quiz": quiz}
