"""Server entry point.

Sets the asyncio event-loop policy on Windows BEFORE the loop is created,
so psycopg's async path works (psycopg requires SelectorEventLoop; Windows
default is ProactorEventLoop, and uvicorn.run() doesn't respect our pre-set
policy — so we drive the loop ourselves via asyncio.run().

Usage (replaces `python -m uvicorn app:app`):
    python run.py
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn


def main() -> None:
    config = uvicorn.Config(
        "app:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
