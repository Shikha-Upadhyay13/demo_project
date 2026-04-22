"""Vector store — dispatches to Chroma (local) or pgvector (Postgres) based on STORAGE_BACKEND.

Public API (unchanged for callers):
    collection_name_for(course_id) -> str
    get_vector_store(course_id)    -> <langchain vector store with .add_texts + .as_retriever>

- STORAGE_BACKEND=sqlite (default) → Chroma persistent client (local dir).
- STORAGE_BACKEND=postgres         → PGVector over the shared Postgres.
"""
from __future__ import annotations

import os

if os.environ.get("STORAGE_BACKEND", "sqlite").strip().lower() == "postgres":
    # Re-export PGVector implementation.
    from store.pg_vector import collection_name_for, get_vector_store  # noqa: F401

else:
    # ─── Chroma implementation (default / rollback path) ──────────────────
    from functools import lru_cache

    import chromadb
    from chromadb.config import Settings
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    CHROMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_data"))
    HF_EMBEDDING_MODEL = os.environ.get(
        "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    @lru_cache(maxsize=1)
    def _client() -> chromadb.ClientAPI:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        return chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False, allow_reset=False),
        )

    @lru_cache(maxsize=1)
    def _embeddings() -> HuggingFaceEmbeddings:
        return HuggingFaceEmbeddings(
            model_name=HF_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def collection_name_for(course_id: str) -> str:
        return f"course_{course_id}"

    def get_vector_store(course_id: str) -> Chroma:
        return Chroma(
            client=_client(),
            collection_name=collection_name_for(course_id),
            embedding_function=_embeddings(),
        )
