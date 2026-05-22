# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest

from arxiv_upvote_trends import search_alphaxiv
from arxiv_upvote_trends.alphaxiv import _get_alphaxiv, extract_alphaxiv_stats


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_returns_papers(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"papers": [{"id": "1"}, {"id": "2"}]},
    )
    result = _get_alphaxiv(page_num=0, wait=0)
    assert result == [{"id": "1"}, {"id": "2"}]
    assert mock_get.call_args.kwargs["timeout"] == 30


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_uses_custom_timeout(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"papers": [{"id": "1"}]},
    )

    _get_alphaxiv(wait=0, timeout=12.5)

    assert mock_get.call_args.kwargs["timeout"] == 12.5


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_raises_on_non_200(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(status_code=500)
    with pytest.raises(Exception, match="Failed to fetch data: 500"):
        _get_alphaxiv(wait=0)


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_raises_on_error_response(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"error": "something went wrong"},
    )
    with pytest.raises(Exception, match="No papers found or error"):
        _get_alphaxiv(wait=0)


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_raises_on_missing_papers_key(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": []},
    )
    with pytest.raises(Exception, match="No papers found or error"):
        _get_alphaxiv(wait=0)


@patch("arxiv_upvote_trends.alphaxiv._get_alphaxiv")
@patch("arxiv_upvote_trends.alphaxiv._PAGE_SIZE", 5)
def test_search_alphaxiv_single_page(mock_get, tmp_path):
    mock_get.return_value = [{"universal_paper_id": "2604.00001"}, {"universal_paper_id": "2604.00002"}]
    result = search_alphaxiv.__wrapped__(max_papers=5, wait=0)
    assert result == [{"universal_paper_id": "2604.00001"}, {"universal_paper_id": "2604.00002"}]
    mock_get.assert_called_once_with(page_num=0, interval="30+Days", wait=0, timeout=30)


def test_extract_alphaxiv_stats():
    paper = {
        "universal_paper_id": "2604.12345",
        "metrics": {"public_total_votes": 42},
    }
    result = extract_alphaxiv_stats(paper)
    assert result == {
        "url": "https://www.alphaxiv.org/abs/2604.12345",
        "arxiv_id": ["2604.12345"],
        "score": 42,
        "num_comments": 0,
    }


def test_extract_alphaxiv_stats_missing_fields():
    result = extract_alphaxiv_stats({})
    assert result == {
        "url": "https://www.alphaxiv.org/abs/",
        "arxiv_id": [""],
        "score": 0,
        "num_comments": 0,
    }


@patch("arxiv_upvote_trends.alphaxiv._get_alphaxiv")
@patch("arxiv_upvote_trends.alphaxiv._PAGE_SIZE", 2)
def test_search_alphaxiv_multiple_pages(mock_get, tmp_path):
    mock_get.side_effect = [
        [{"universal_paper_id": "2604.00001"}],
        [{"universal_paper_id": "2604.00002"}],
        [{"universal_paper_id": "2604.00003"}],
    ]
    result = search_alphaxiv.__wrapped__(max_papers=6, wait=0)
    assert result == [
        {"universal_paper_id": "2604.00001"},
        {"universal_paper_id": "2604.00002"},
        {"universal_paper_id": "2604.00003"},
    ]
    assert mock_get.call_count == 3


@patch("arxiv_upvote_trends.alphaxiv._get_alphaxiv")
@patch("arxiv_upvote_trends.alphaxiv._PAGE_SIZE", 2)
def test_search_alphaxiv_deduplicates_papers_before_slicing(mock_get, tmp_path):
    mock_get.side_effect = [
        [
            {"universal_paper_id": "2604.00001", "title": "First"},
            {"universal_paper_id": "2604.00002", "title": "Second"},
        ],
        [
            {"universal_paper_id": "2604.00002", "title": "Second duplicate"},
            {"universal_paper_id": "2604.00003", "title": "Third"},
        ],
    ]

    result = search_alphaxiv.__wrapped__(max_papers=4, wait=0)

    assert result == [
        {"universal_paper_id": "2604.00001", "title": "First"},
        {"universal_paper_id": "2604.00002", "title": "Second"},
        {"universal_paper_id": "2604.00003", "title": "Third"},
    ]
