"""Night-before script — pre-generates the 4 demo seed courses.

Run once the day before the demo so the catalog page isn't empty and you
have a known-good backup if live generation hits an issue during the review.

Usage:
    python scripts/pregen_courses.py
    python scripts/pregen_courses.py --topics "GraphQL basics" "Tailwind CSS"
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pregen")


DEFAULT_TOPICS = [
    "Docker basics",
    "React Hooks",
    "Python decorators",
    "Kubernetes pods",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--topics", nargs="+", default=None, help="Topics to pre-generate.")
    args = p.parse_args()
    topics = args.topics or DEFAULT_TOPICS

    from graphs.course_builder import compiled_course_builder
    from store import catalog

    graph = compiled_course_builder()

    for topic in topics:
        course_id = f"crs_{uuid.uuid4().hex[:10]}"
        log.info("Pre-generating %r as %s", topic, course_id)
        started = time.perf_counter()
        try:
            final = graph.invoke(
                {"course_id": course_id, "topic": topic},
                config={"configurable": {"thread_id": course_id}},
            )
        except Exception as e:
            log.error("Failed on %r: %s", topic, e)
            continue

        payload = {
            "videos": final.get("videos", []),
            "transcripts": final.get("transcripts", []),
            "summary": final.get("summary", ""),
            "quiz": final.get("quiz", []),
        }
        catalog.upsert(course_id=course_id, topic=topic, payload=payload)
        log.info(
            "OK %r in %.1fs — %d videos, %d quiz questions",
            topic,
            time.perf_counter() - started,
            len(payload["videos"]),
            len(payload["quiz"]),
        )


if __name__ == "__main__":
    main()
