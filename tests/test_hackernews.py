# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest

from arxiv_upvote_trends import search_hackernews
from arxiv_upvote_trends.hackernews import _get_hackernews, extract_hackernews_stats


@patch("arxiv_upvote_trends.hackernews.time.sleep")
@patch("arxiv_upvote_trends.hackernews.requests.get")
def test__get_hackernews_returns_papers_with_arxiv_urls(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "hits": [
                {"objectID": "1", "url": "https://arxiv.org/abs/2604.00001", "points": 10, "num_comments": 2},
                {"objectID": "2", "url": "https://example.com", "points": 5, "num_comments": 0},
                {"objectID": "3", "url": "https://arxiv.org/pdf/2604.00002", "points": 8, "num_comments": 1},
            ]
        },
    )

    result = _get_hackernews(wait=0)

    assert len(result) == 2
    assert result[0]["objectID"] == "1"
    assert result[1]["objectID"] == "3"


@patch("arxiv_upvote_trends.hackernews.time.sleep")
@patch("arxiv_upvote_trends.hackernews.requests.get")
def test__get_hackernews_filters_hits_without_url(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "hits": [
                {"objectID": "1", "url": None, "points": 10},
                {"objectID": "2", "points": 5},
            ]
        },
    )

    result = _get_hackernews(wait=0)

    assert result == []


@patch("arxiv_upvote_trends.hackernews.time.sleep")
@patch("arxiv_upvote_trends.hackernews.requests.get")
def test__get_hackernews_raises_on_non_200(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(status_code=500)

    with pytest.raises(Exception, match="Failed to fetch data: 500"):
        _get_hackernews(wait=0)


@patch("arxiv_upvote_trends.hackernews.time.sleep")
@patch("arxiv_upvote_trends.hackernews.requests.get")
def test__get_hackernews_raises_on_missing_hits_key(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"results": []},
    )

    with pytest.raises(Exception, match="No hits found or error"):
        _get_hackernews(wait=0)


@patch("arxiv_upvote_trends.hackernews.time.sleep")
@patch("arxiv_upvote_trends.hackernews.requests.get")
def test__get_hackernews_uses_custom_timeout(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"hits": []},
    )

    _get_hackernews(wait=0, timeout=15)

    assert mock_get.call_args.kwargs["timeout"] == 15


@patch("arxiv_upvote_trends.hackernews._get_hackernews")
def test_search_hackernews_deduplicates_papers(mock_get):
    mock_get.return_value = [
        {"objectID": "1", "url": "https://arxiv.org/abs/2604.00001"},
        {"objectID": "1", "url": "https://arxiv.org/abs/2604.00001"},
        {"objectID": "2", "url": "https://arxiv.org/abs/2604.00002"},
    ]

    result = search_hackernews.__wrapped__(max_papers=300, wait=0)

    assert len(result) == 2
    assert result[0]["objectID"] == "1"
    assert result[1]["objectID"] == "2"


@patch("arxiv_upvote_trends.hackernews._get_hackernews")
def test_search_hackernews_slices_to_max_papers(mock_get):
    mock_get.return_value = [{"objectID": str(i), "url": f"https://arxiv.org/abs/2604.{i:05}"} for i in range(10)]

    result = search_hackernews.__wrapped__(max_papers=3, wait=0)

    assert len(result) == 3


def test_extract_hackernews_stats():
    paper = {
        "objectID": "12345",
        "url": "https://arxiv.org/abs/2604.00001",
        "points": 42,
        "num_comments": 7,
    }

    result = extract_hackernews_stats(paper)

    assert result == {
        "url": "https://news.ycombinator.com/item?id=12345",
        "arxiv_id": ["2604.00001"],
        "score": 42,
        "num_comments": 7,
    }


def test_extract_hackernews_stats_splits_score_for_multiple_ids():
    paper = {
        "objectID": "12345",
        "url": "https://arxiv.org/abs/2604.00001 https://arxiv.org/abs/2604.00002",
        "points": 10,
        "num_comments": 3,
    }

    result = extract_hackernews_stats(paper)

    assert result == {
        "url": "https://news.ycombinator.com/item?id=12345",
        "arxiv_id": ["2604.00001", "2604.00002"],
        "score": 5,
        "num_comments": 3,
    }


def test_extract_hackernews_stats_missing_fields():
    result = extract_hackernews_stats({})

    assert result == {
        "url": "https://news.ycombinator.com/item?id=",
        "arxiv_id": [],
        "score": 0,
        "num_comments": 0,
    }
