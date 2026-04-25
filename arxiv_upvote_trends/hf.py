# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from huggingface_hub import HfApi

from .cache import fallback_cache

logger = logging.getLogger(__name__)


_PAGE_SIZE = 100
_MAX_DAILY_PAPERS = 300


def _get_huggingface(api: HfApi, date: str, wait: float = 1.0) -> list[dict]:
    """Fetch one date of Hugging Face Daily Papers with pagination."""
    logger.info("Fetching papers for date %s", date)
    all_papers = []
    p = 0
    while len(all_papers) < _MAX_DAILY_PAPERS:
        time.sleep(wait)
        papers = list(api.list_daily_papers(date=date, limit=_PAGE_SIZE, p=p))
        logger.info("Fetched %s papers for date %s page %s", len(papers), date, p)
        all_papers.extend(papers)
        if len(papers) < _PAGE_SIZE:
            break
        p += 1
    return [asdict(paper) for paper in all_papers[:_MAX_DAILY_PAPERS]]


@fallback_cache()
def search_huggingface(max_papers: int = 300, days: int = 30, wait: float = 1.0) -> list[dict]:
    """Fetch recent papers from Hugging Face Daily Papers.

    Iterates from the most recent date backwards, stopping once max_papers is reached.
    Falls back to the cached result via fallback_cache when the API is unavailable.
    """
    api = HfApi()
    now = datetime.now(tz=UTC)
    dates = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(days)]
    logger.info("Searching Hugging Face for papers: %s", dates)
    all_papers = []
    for date in dates:
        all_papers.extend(_get_huggingface(api, date=date, wait=wait))
        if len(all_papers) >= max_papers:
            break
    return all_papers[:max_papers]


def extract_huggingface_stats(paper: dict) -> dict:
    """Extract ranking stats from a Hugging Face Daily Paper."""
    arxiv_id = str(paper.get("id") or "")
    return {
        "url": f"https://huggingface.co/papers/{arxiv_id}",
        "arxiv_id": [arxiv_id],
        "score": int(paper.get("upvotes") or 0),
        "num_comments": int(paper.get("comments") or 0),
    }
