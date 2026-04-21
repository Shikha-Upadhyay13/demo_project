"""LLM-as-judge evaluator + experiment runner for quiz quality.

Usage (after ``python evals/dataset.py``):

    python evals/evaluators.py          # run one experiment on the current live prompt
    python evals/evaluators.py --both   # run both SUMMARY_PROMPT_V1 and V2 for comparison

The "both" mode swaps the active summary prompt, which is how we produce the
v1-vs-v2 experiment the PRD §6.3 claims as a deliverable. We piggyback on the
quiz-quality eval (same pipeline) so the comparison is produced from one run.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langsmith import Client
from pydantic import BaseModel, Field

from evals.dataset import DATASET_NAME


class QuizScore(BaseModel):
    relevance: float = Field(ge=0, le=1, description="How topical are the questions to the subject?")
    difficulty: float = Field(ge=0, le=1, description="Appropriate spread from beginner to harder?")
    non_triviality: float = Field(ge=0, le=1, description="Do questions avoid pure definition/trivia?")
    reasoning: str


JUDGE_PROMPT = """You are grading the quality of a 5-question multiple choice quiz generated for the
topic: {topic}.

The expected content coverage hints are:
{criteria}

The quiz (JSON):
---
{quiz}
---

Score each dimension from 0.0 to 1.0:
- relevance: are the questions actually about the topic?
- difficulty: is there a reasonable spread of difficulty, not all easy, not all impossibly hard?
- non_triviality: do the questions test understanding rather than pure definitions or trivia?

Then write 1-3 sentences of reasoning."""


def _judge(topic: str, criteria: str, quiz: list[dict]) -> QuizScore:
    prompt = ChatPromptTemplate.from_template(
        JUDGE_PROMPT
        + '\n\nReturn ONLY a JSON object: {{"relevance": 0.0-1.0, "difficulty": 0.0-1.0, "non_triviality": 0.0-1.0, "reasoning": "<text>"}}'
    )
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    chain = prompt | llm.with_structured_output(QuizScore, method="json_mode")
    import json as _json
    return chain.invoke({"topic": topic, "criteria": criteria, "quiz": _json.dumps(quiz)})


def quiz_quality_score(run, example) -> dict:
    """LangSmith evaluator callable.

    run.outputs["quiz"]     — quiz produced by the target function.
    example.inputs["topic"] — seed topic.
    example.outputs["criteria"] — coverage hint.
    """
    quiz = run.outputs.get("quiz", [])
    topic = example.inputs.get("topic", "")
    criteria = (example.outputs or {}).get("criteria", "")
    if not quiz:
        return {"key": "quiz_quality", "score": 0.0, "comment": "no quiz produced"}

    score = _judge(topic, criteria, quiz)
    aggregate = (score.relevance + score.difficulty + score.non_triviality) / 3.0
    return {
        "key": "quiz_quality",
        "score": round(aggregate, 3),
        "comment": score.reasoning,
        "correction": None,
    }


def _target(inputs: dict) -> dict:
    """Target function for the LangSmith experiment: run just the quiz_generator node."""
    from graphs.course_builder import compiled_course_builder

    topic = inputs["topic"]
    course_id = f"eval_{uuid.uuid4().hex[:8]}"
    graph = compiled_course_builder()
    final = graph.invoke(
        {"course_id": course_id, "topic": topic},
        config={"configurable": {"thread_id": course_id}},
    )
    return {"quiz": final.get("quiz", []), "summary": final.get("summary", "")}


def run_experiment(label: str) -> None:
    client = Client()
    client.evaluate(
        _target,
        data=DATASET_NAME,
        evaluators=[quiz_quality_score],
        experiment_prefix=label,
    )
    print(f"Experiment {label!r} submitted. Open LangSmith → {DATASET_NAME} → Experiments.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--both", action="store_true", help="Run v1 and v2 of the summary prompt.")
    args = p.parse_args()

    if args.both:
        # Flip the active summary prompt and re-run. The quiz generator is unaffected, but since we
        # run the full graph, summary quality changes alongside — the experiment visualizes both
        # pipelines end-to-end.
        from nodes import generation

        generation.ACTIVE_SUMMARY_PROMPT = generation.SUMMARY_PROMPT_V1
        run_experiment("summary_prompt_v1")

        generation.ACTIVE_SUMMARY_PROMPT = generation.SUMMARY_PROMPT_V2
        run_experiment("summary_prompt_v2")
    else:
        run_experiment("quiz_quality_baseline")


if __name__ == "__main__":
    main()
