"""YouTube search + transcript fetching nodes.

Both are pure I/O — no LLM calls. They populate `videos` and `transcripts`
in CourseState.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

log = logging.getLogger(__name__)

# Number of search candidates — overfetch so we still have >=3 after captionless drops.
SEARCH_CANDIDATES = 5
MIN_USABLE_VIDEOS = 2


def _yt_client():
    key = os.environ["YOUTUBE_API_KEY"]
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


def video_finder(state: dict) -> dict:
    """Search YouTube Data API for tutorial videos about `topic`.

    Filters for English, medium-length, ordered by relevance. Returns up to
    SEARCH_CANDIDATES video metadata dicts.
    """
    topic = state["topic"]
    yt = _yt_client()

    search = (
        yt.search()
        .list(
            q=f"{topic} tutorial",
            part="snippet",
            type="video",
            videoDuration="medium",
            relevanceLanguage="en",
            order="relevance",
            maxResults=SEARCH_CANDIDATES,
            safeSearch="strict",
        )
        .execute()
    )

    videos: list[dict[str, Any]] = []
    for item in search.get("items", []):
        vid_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append(
            {
                "id": vid_id,
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
            }
        )

    log.info("video_finder: topic=%r found=%d", topic, len(videos))
    return {"videos": videos}


def _group_into_sentences(lines: list[str], target_words: int = 15) -> str:
    """Group caption lines into pseudo-sentences so chunkers have real boundaries.

    YouTube captions arrive as ~5-15-word fragments without punctuation. A naive
    character-level splitter can't find sentence boundaries, so chunks cut
    mid-concept. We merge adjacent lines into groups of roughly ``target_words``
    and append a period — giving RecursiveCharacterTextSplitter real "." anchors
    to split on.
    """
    groups: list[str] = []
    buf: list[str] = []
    words = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        buf.append(line)
        words += len(line.split())
        if words >= target_words:
            groups.append(" ".join(buf).rstrip(".!?") + ".")
            buf, words = [], 0
    if buf:
        groups.append(" ".join(buf).rstrip(".!?") + ".")
    # Newlines between groups — splitter sees them as paragraph breaks.
    return "\n\n".join(groups)


def _fetch_one(video_id: str) -> str | None:
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB"])
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        log.warning("transcript unavailable for %s: %s", video_id, type(e).__name__)
        return None
    except Exception as e:
        log.warning("transcript fetch failed for %s: %s", video_id, e)
        return None

    lines = [snippet.text for snippet in fetched]
    text = _group_into_sentences(lines)
    return text or None


def transcript_fetcher(state: dict) -> dict:
    """Fetch captions for each candidate video. Drop any that fail.

    Mutates `videos` to only those with usable transcripts so downstream nodes
    see the same count. Raises ValueError if fewer than MIN_USABLE_VIDEOS remain —
    the API layer surfaces this as a friendly retry message.
    """
    usable_videos: list[dict[str, Any]] = []
    transcripts: list[str] = []

    for v in state["videos"]:
        text = _fetch_one(v["id"])
        if text:
            usable_videos.append(v)
            transcripts.append(text)
        if len(usable_videos) >= 3:
            # We only need 3 good ones — stop once we have them to save quota + time.
            break

    if len(usable_videos) < MIN_USABLE_VIDEOS:
        raise ValueError(
            f"Only {len(usable_videos)} video(s) with usable captions for "
            f"{state.get('topic')!r}. Need at least {MIN_USABLE_VIDEOS}."
        )

    log.info("transcript_fetcher: kept=%d dropped=%d",
             len(usable_videos), len(state["videos"]) - len(usable_videos))
    return {"videos": usable_videos, "transcripts": transcripts}
