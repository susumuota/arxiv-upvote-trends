# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import math
import time
from itertools import chain

import requests

from .cache import fallback_cache

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_SORT_BY = "Likes"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/146.0.0.0 Safari/537.36"
)


def _get_alphaxiv(
    page_num: int = 0,
    interval: str = "30+Days",
    wait: float = 1.0,
) -> list[dict]:
    """Fetch a single page of papers from the alphaXiv API.

    Args:
        page_num: Zero-based page number to fetch.
        interval: Time range filter (e.g. "3+Days", "7+Days", "30+Days", "90+Days", "All+time").
        wait: Seconds to wait before making the request.

    Returns:
        A list of paper dicts.

    Raises:
        Exception: If the API returns an error.
    """
    url = f"https://api.alphaxiv.org/papers/v3/feed?pageNum={page_num}&sort={_SORT_BY}&pageSize={_PAGE_SIZE}&interval={interval}&topics=%5B%5D"
    referer = f"https://www.alphaxiv.org/?interval={interval}&sort={_SORT_BY}"
    time.sleep(wait)
    response = requests.get(url, headers={"Referer": referer, "User-Agent": _USER_AGENT})
    logger.info(f"Fetched page {page_num} with status code {response.status_code}")
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code}")
    js = response.json()
    if not js or "error" in js or "papers" not in js:
        raise Exception(f"No papers found or error in response: {js}")
    papers = js["papers"]
    logger.info(f"Fetched {len(papers)} papers from page {page_num}")
    return papers


@fallback_cache()
def search_alphaxiv(
    max_papers: int = 300,
    interval: str = "30+Days",
    wait: float = 1.0,
) -> list[dict]:
    """Fetch trending papers from alphaXiv with pagination.

    Falls back to the cached result via fallback_cache when the API is unavailable.

    Args:
        max_papers: Maximum number of papers to fetch.
        interval: Time range filter (e.g. "3+Days", "7+Days", "30+Days", "90+Days", "All+time").
        wait: Seconds to wait before each request.

    Returns:
        A list of paper dicts (up to max_papers).
    """
    total_pages = math.ceil(max_papers / _PAGE_SIZE)
    pages = [_get_alphaxiv(page_num=page_num, interval=interval, wait=wait) for page_num in range(total_pages)]
    return list(chain.from_iterable(pages))[:max_papers]
