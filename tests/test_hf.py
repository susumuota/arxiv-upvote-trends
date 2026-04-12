# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from arxiv_upvote_trends.hf import _get_huggingface, extract_huggingface_stats


@dataclass
class FakePaper:
    title: str
    paper_id: str


@patch("arxiv_upvote_trends.hf.time.sleep")
def test_returns_list_of_dicts(mock_sleep):
    api = MagicMock()
    api.list_daily_papers.return_value = [
        FakePaper(title="Paper A", paper_id="2401.00001"),
        FakePaper(title="Paper B", paper_id="2401.00002"),
    ]
    result = _get_huggingface(api, "2026-04-01")
    assert result == [
        {"title": "Paper A", "paper_id": "2401.00001"},
        {"title": "Paper B", "paper_id": "2401.00002"},
    ]
    api.list_daily_papers.assert_called_once_with(date="2026-04-01", limit=100, p=0)


@patch("arxiv_upvote_trends.hf.time.sleep")
def test_returns_empty_list_when_no_papers(mock_sleep):
    api = MagicMock()
    api.list_daily_papers.return_value = []
    result = _get_huggingface(api, "2026-04-01")
    assert result == []


@patch("arxiv_upvote_trends.hf.time.sleep")
def test_respects_wait_parameter(mock_sleep):
    api = MagicMock()
    api.list_daily_papers.return_value = []
    _get_huggingface(api, "2026-04-01", wait=2.5)
    mock_sleep.assert_called_once_with(2.5)


def test_extract_huggingface_stats():
    paper = {
        "id": "2604.12345",
        "upvotes": 10,
        "comments": 3,
    }
    result = extract_huggingface_stats(paper)
    assert result == {
        "url": "https://huggingface.co/papers/2604.12345",
        "arxiv_id": ["2604.12345"],
        "score": 10,
        "num_comments": 3,
    }


def test_extract_huggingface_stats_missing_fields():
    result = extract_huggingface_stats({})
    assert result == {
        "url": "https://huggingface.co/papers/",
        "arxiv_id": [""],
        "score": 0,
        "num_comments": 0,
    }
