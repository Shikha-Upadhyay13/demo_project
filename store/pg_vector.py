"""Postgres + pgvector replacement for store/chroma_client.py.

Public API matches chroma_client.py exactly:
    collection_name_for(course_id) -> str
    get_vector_store(course_id) -> <langchain vector store>

The returned object supports `.add_texts(texts, metadatas)` and
`.as_retriever(search_kwargs={'k': N})` — the two methods actually used
by nodes/indexing.py and nodes/chat.py.

One PGVector "collection" per course_id. PGVector stores embeddings in
two tables (`langchain_pg_collection`, `langchain_pg_embedding`) with a
collection_id FK — the one-collection-per-course pattern maps cleanly.
"""
from __future__ import annotations

import os
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector

HF_EMBEDDING_MODEL = os.environ.get(
    "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Required when STORAGE_BACKEND=postgres."
        )
    # langchain_postgres requires the `postgresql+psycopg://` driver form.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    # Same local embedding model as the SQLite/Chroma path — keeps vectors compatible
    # in dimension (384) so we could in theory migrate existing data.
    return HuggingFaceEmbeddings(
        model_name=HF_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def collection_name_for(course_id: str) -> str:
    return f"course_{course_id}"


def get_vector_store(course_id: str) -> PGVector:
    """Return a PGVector wrapper for the per-course collection."""
    return PGVector(
        embeddings=_embeddings(),
        collection_name=collection_name_for(course_id),
        connection=_db_url(),
        use_jsonb=True,
    )
