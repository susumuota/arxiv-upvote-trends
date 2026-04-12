# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest

from arxiv_upvote_trends import search_alphaxiv
from arxiv_upvote_trends.alphaxiv import _get_alphaxiv


@patch("arxiv_upvote_trends.alphaxiv.time.sleep")
@patch("arxiv_upvote_trends.alphaxiv.requests.get")
def test__get_alphaxiv_returns_papers(mock_get, mock_sleep):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"papers": [{"id": "1"}, {"id": "2"}]},
    )
    result = _get_alphaxiv(page_num=0, wait=0)
    assert result == [{"id": "1"}, {"id": "2"}]


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
    mock_get.return_value = [{"id": "1"}, {"id": "2"}]
    result = search_alphaxiv.__wrapped__(max_papers=5, wait=0)
    assert result == [{"id": "1"}, {"id": "2"}]
    mock_get.assert_called_once_with(page_num=0, interval="30+Days", wait=0)


@patch("arxiv_upvote_trends.alphaxiv._get_alphaxiv")
@patch("arxiv_upvote_trends.alphaxiv._PAGE_SIZE", 2)
def test_search_alphaxiv_multiple_pages(mock_get, tmp_path):
    mock_get.side_effect = [
        [{"id": "1"}],
        [{"id": "2"}],
        [{"id": "3"}],
    ]
    result = search_alphaxiv.__wrapped__(max_papers=6, wait=0)
    assert result == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert mock_get.call_count == 3
