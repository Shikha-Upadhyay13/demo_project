"""Transcript chunking + embedding node.

Single node that splits all transcripts, embeds them, and stores in a
per-course Chroma collection.
"""
from __future__ import annotations

import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from store.chroma_client import collection_name_for, get_vector_store

log = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 300


def chunker_embedder(state: dict) -> dict:
    """Split transcripts and push embeddings to Chroma.

    Attaches per-chunk metadata {video_idx, video_id, video_title} so
    retrieve_and_answer can cite sources later.
    """
    course_id = state["course_id"]
    transcripts = state["transcripts"]
    videos = state["videos"]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    texts: list[str] = []
    metadatas: list[dict] = []

    for idx, (video, transcript) in enumerate(zip(videos, transcripts)):
        chunks = splitter.split_text(transcript)
        for chunk in chunks:
            texts.append(chunk)
            metadatas.append(
                {
                    "video_idx": idx,
                    "video_id": video["id"],
                    "video_title": video["title"],
                }
            )

    vs = get_vector_store(course_id)
    vs.add_texts(texts=texts, metadatas=metadatas)

    log.info(
        "chunker_embedder: course=%s videos=%d chunks=%d",
        course_id, len(videos), len(texts),
    )
    return {"vector_collection_name": collection_name_for(course_id)}
