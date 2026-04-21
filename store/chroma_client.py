"""Singleton Chroma persistent client.

One collection per course, keyed by `course_id`, so the two graphs share
retrieval state without sharing LangGraph state.
"""
from __future__ import annotations

import os
from functools import lru_cache

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

CHROMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_data"))
HF_EMBEDDING_MODEL = os.environ.get("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _client() -> chromadb.ClientAPI:
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    # Local embeddings — no API key, first call downloads ~90MB, cached after.
    return HuggingFaceEmbeddings(
        model_name=HF_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def collection_name_for(course_id: str) -> str:
    return f"course_{course_id}"


def get_vector_store(course_id: str) -> Chroma:
    """Return a LangChain Chroma wrapper for a course's collection."""
    return Chroma(
        client=_client(),
        collection_name=collection_name_for(course_id),
        embedding_function=_embeddings(),
    )
