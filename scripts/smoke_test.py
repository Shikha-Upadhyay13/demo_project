"""CLI smoke test: run the Course Builder end-to-end against a real topic.

Usage:
    python scripts/smoke_test.py "Docker basics"

Prints videos found, transcript sizes, summary head, and quiz JSON.
Used in hour 0:45–2:00 of the PRD §7 build timeline before any HTTP exists.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path

# Make the project root importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/smoke_test.py "<topic>"', file=sys.stderr)
        sys.exit(2)

    topic = sys.argv[1]
    course_id = f"smoke_{uuid.uuid4().hex[:8]}"

    # Import after dotenv/sys.path so env is loaded first.
    from graphs.course_builder import compiled_course_builder
    from store import catalog

    graph = compiled_course_builder()
    config = {"configurable": {"thread_id": course_id}}

    print(f"\n=== Smoke test: topic={topic!r} course_id={course_id} ===\n")
    started = time.perf_counter()

    final = graph.invoke({"course_id": course_id, "topic": topic}, config=config)

    elapsed = time.perf_counter() - started
    print(f"\n--- Completed in {elapsed:.1f}s ---")
    print(f"Videos: {len(final.get('videos', []))}")
    for v in final.get("videos", []):
        print(f"  - {v['title']}  ({v['url']})")
    print(f"Transcripts: {[len(t) for t in final.get('transcripts', [])]} chars each")
    summary = final.get("summary", "")
    print("\nSummary (head):\n" + "\n".join(summary.splitlines()[:12]))
    print("\nQuiz:")
    for i, q in enumerate(final.get("quiz", []), start=1):
        print(f"  Q{i}. {q['q']}")
        for j, opt in enumerate(q["options"]):
            marker = "*" if j == q["correct_idx"] else " "
            print(f"    {marker} {j}. {opt}")

    # Persist so the catalog page can see it immediately.
    payload = {
        "videos": final.get("videos", []),
        "transcripts": final.get("transcripts", []),
        "summary": final.get("summary", ""),
        "quiz": final.get("quiz", []),
    }
    catalog.upsert(course_id=course_id, topic=topic, payload=payload)
    print(f"\nPersisted course to catalog: {course_id}")

    # Raw JSON for piping if desired.
    if "--json" in sys.argv:
        print("\n--- JSON ---")
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
