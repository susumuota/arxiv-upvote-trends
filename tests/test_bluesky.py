# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from atproto.exceptions import AtProtocolError

from arxiv_upvote_trends.bluesky import MAX_POST_LENGTH, build_bluesky_post, post_to_bluesky
from arxiv_upvote_trends.report import ReportRow


def test_build_bluesky_post_includes_top_rows_and_url():
    rows = [
        _row(rank=1, arxiv_id="2604.00001", title="First paper", score=123),
        _row(rank=2, arxiv_id="2604.00002", title="Second paper", score=45),
    ]

    text = build_bluesky_post(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC), limit=5)

    assert len(text) <= MAX_POST_LENGTH
    assert "arXiv Upvote Trends Top 2" in text
    assert "1. First paper (123 pts)" in text
    assert "2. Second paper (45 pts)" in text
    assert "Top paper: https://arxiv.org/abs/2604.00001" in text
    assert "Generated 2026-04-23 00:00 UTC" in text


def test_build_bluesky_post_truncates_long_titles():
    rows = [
        _row(
            rank=index,
            arxiv_id=f"2604.{index:05}",
            title="A very long paper title that should be shortened before posting to Bluesky",
            score=1000 - index,
        )
        for index in range(1, 6)
    ]

    text = build_bluesky_post(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC), limit=5)

    assert len(text) <= MAX_POST_LENGTH
    assert "..." in text
    assert "Top paper: https://arxiv.org/abs/2604.00001" in text


def test_build_bluesky_post_handles_empty_rows():
    text = build_bluesky_post([], generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert len(text) <= MAX_POST_LENGTH
    assert text == "arXiv Upvote Trends\nNo papers found.\nGenerated 2026-04-23 00:00 UTC"


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_logs_in_and_sends_post(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    result = post_to_bluesky("hello")

    mock_client_cls.assert_called_once_with(base_url="https://bsky.social")
    mock_client.login.assert_called_once_with(login="user.bsky.social", password="app-password")
    mock_client.send_post.assert_called_once_with("hello")
    assert result.uri == "at://did/example"
    assert result.cid == "cid-value"


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_uses_configured_service_url(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    monkeypatch.setenv("BLUESKY_SERVICE_URL", "https://example.test")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky("hello")

    mock_client_cls.assert_called_once_with(base_url="https://example.test")


def test_post_to_bluesky_requires_credentials(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    with pytest.raises(ValueError, match="BLUESKY_HANDLE"):
        post_to_bluesky("hello")

    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="BLUESKY_APP_PASSWORD"):
        post_to_bluesky("hello")


def test_post_to_bluesky_rejects_long_text():
    with pytest.raises(ValueError, match="300"):
        post_to_bluesky("x" * 301)


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sanitizes_atproto_errors(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.login.side_effect = AtProtocolError("request failed with app-password")

    with pytest.raises(RuntimeError) as exc_info:
        post_to_bluesky("hello")

    assert str(exc_info.value) == "Failed to post to Bluesky: AtProtocolError"
    assert "app-password" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sanitizes_send_post_errors(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.side_effect = AtProtocolError("post failed with app-password")

    with pytest.raises(RuntimeError) as exc_info:
        post_to_bluesky("hello")

    assert str(exc_info.value) == "Failed to post to Bluesky: AtProtocolError"
    assert "app-password" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def _row(rank: int, arxiv_id: str, title: str, score: int) -> ReportRow:
    return ReportRow(
        rank=rank,
        arxiv_id=arxiv_id,
        title=title,
        authors="",
        score=score,
        num_comments=0,
        count=1,
        alphaxiv_score=score,
        huggingface_score=0,
        huggingface_comments=0,
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        alphaxiv_url=f"https://www.alphaxiv.org/abs/{arxiv_id}",
        huggingface_url=f"https://huggingface.co/papers/{arxiv_id}",
        source_urls=(),
    )
