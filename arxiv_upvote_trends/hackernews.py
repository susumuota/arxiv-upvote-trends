# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import time
from datetime import UTC, datetime, timedelta

import requests

from .arxiv import parse_arxiv_ids
from .cache import fallback_cache
from .dedupe import deduplicate

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30


def _get_hackernews(
    max_papers: int = 300,
    days: int = 30,
    wait: float = 1.0,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch Hacker News posts linking to arxiv.org after a throttling delay."""
    params: dict[str, str] = {
        "query": "arxiv.org",
        "restrictSearchableAttributes": "url",
        "hitsPerPage": str(max_papers),
    }
    if days > 0:
        cutoff = int((datetime.now(UTC) - timedelta(days=days)).timestamp())
        params["numericFilters"] = f"created_at_i>{cutoff}"
    time.sleep(wait)
    response = requests.get(
        "https://hn.algolia.com/api/v1/search",
        params=params,
        timeout=timeout,
    )
    logger.info("Fetched Hacker News with status code %s", response.status_code)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code}")
    js = response.json()
    if not js or "hits" not in js:
        raise Exception(f"No hits found or error in response: {js}")
    hits = js["hits"]
    papers = [hit for hit in hits if hit.get("url") and parse_arxiv_ids(hit["url"])]
    logger.info("Fetched %s papers from Hacker News (%s hits total)", len(papers), len(hits))
    return papers


@fallback_cache()
def search_hackernews(
    max_papers: int = 300,
    days: int = 30,
    wait: float = 1.0,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch Hacker News posts linking to arXiv papers.

    Falls back to the cached result via fallback_cache when the API is unavailable.
    """
    papers = _get_hackernews(max_papers=max_papers, days=days, wait=wait, timeout=timeout)
    return deduplicate(papers, key=_post_id)[:max_papers]


def _post_id(paper: dict) -> str | None:
    return str(paper.get("objectID") or "") or None


def extract_hackernews_stats(paper: dict) -> dict:
    """Extract ranking stats from a Hacker News post."""
    object_id = str(paper.get("objectID") or "")
    url = str(paper.get("url") or "")
    arxiv_ids = parse_arxiv_ids(url)
    points = int(paper.get("points") or 0)
    score = points // len(arxiv_ids) if arxiv_ids else points
    return {
        "url": f"https://news.ycombinator.com/item?id={object_id}",
        "arxiv_id": arxiv_ids,
        "score": score,
        "num_comments": int(paper.get("num_comments") or 0),
    }
