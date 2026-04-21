"""Create the 5-topic LangSmith dataset for the quiz-quality experiment.

Usage:
    python evals/dataset.py

Creates a dataset named 'adaptivai-mini-topics' with 5 input examples. The
evaluator (evals/evaluators.py) reads quiz outputs against these inputs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client

DATASET_NAME = "adaptivai-mini-topics"

EXAMPLES = [
    {
        "topic": "Docker basics",
        "criteria": "Image vs container; layers; Dockerfile basics; volumes; when to use Docker.",
    },
    {
        "topic": "React Hooks",
        "criteria": "useState, useEffect, useMemo; rules of hooks; stale closures; custom hooks.",
    },
    {
        "topic": "Python decorators",
        "criteria": "Function wrapping; @ syntax; decorator factories; functools.wraps; when to use.",
    },
    {
        "topic": "Kubernetes pods",
        "criteria": "Pod vs container; lifecycle; multi-container pods; networking basics.",
    },
    {
        "topic": "Git rebase",
        "criteria": "Rebase vs merge; interactive rebase; when to rebase vs not; conflict resolution.",
    },
]


def main() -> None:
    client = Client()
    existing = None
    for ds in client.list_datasets(dataset_name=DATASET_NAME):
        existing = ds
        break
    if existing:
        print(f"Dataset {DATASET_NAME!r} already exists (id={existing.id}); skipping create.")
        ds = existing
    else:
        ds = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Seed topics for AdaptivAI Mini quiz-quality evaluation.",
        )
        print(f"Created dataset {DATASET_NAME!r} (id={ds.id})")

    # Upsert examples.
    existing_inputs = {e.inputs.get("topic") for e in client.list_examples(dataset_id=ds.id)}
    added = 0
    for ex in EXAMPLES:
        if ex["topic"] in existing_inputs:
            continue
        client.create_example(
            inputs={"topic": ex["topic"]},
            outputs={"criteria": ex["criteria"]},
            dataset_id=ds.id,
        )
        added += 1
    print(f"Added {added} new example(s). Total examples now: {len(EXAMPLES)}.")


if __name__ == "__main__":
    main()
