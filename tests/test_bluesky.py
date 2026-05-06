# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from atproto.exceptions import AtProtocolError
from atproto_client.models.blob_ref import BlobRef
from PIL import Image

from arxiv_upvote_trends.bluesky import (
    MAX_IMAGE_BYTES,
    MAX_POST_LENGTH,
    build_bluesky_paper_post,
    build_bluesky_report_post,
    post_to_bluesky,
)
from arxiv_upvote_trends.report import ReportRow


def test_build_bluesky_paper_post_includes_row_details_and_url():
    row = _row(rank=2, arxiv_id="2604.00002", title="Second paper", score=45)

    text = build_bluesky_paper_post(row)

    assert len(text) <= MAX_POST_LENGTH
    assert "New arXiv Upvote Trends paper" in text
    assert "Rank 2: Second paper" in text
    assert "45 pts" in text
    assert "https://arxiv.org/abs/2604.00002" in text


def test_build_bluesky_paper_post_truncates_long_titles():
    row = _row(
        rank=1,
        arxiv_id="2604.00001",
        title="A very long paper title that should be shortened before posting to Bluesky " * 20,
        score=123,
    )

    text = build_bluesky_paper_post(row)

    assert len(text) <= MAX_POST_LENGTH
    assert "..." in text
    assert "https://arxiv.org/abs/2604.00001" in text


def test_build_bluesky_report_post_includes_report_summary():
    rows = [
        _row(rank=1, arxiv_id="2604.00001", title="First paper", score=123),
        _row(rank=2, arxiv_id="2604.00002", title="Second paper", score=45),
    ]

    text = build_bluesky_report_post(rows)

    assert len(text) <= MAX_POST_LENGTH
    assert "arXiv Upvote Trends Top 30" in text
    assert "2 papers" in text
    assert "total upvotes 168" in text
    assert "Top paper: https://arxiv.org/abs/2604.00001" in text


def test_build_bluesky_report_post_handles_empty_rows():
    assert build_bluesky_report_post([]) == "arXiv Upvote Trends Top 30\nNo papers found."


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


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_attaches_images(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    Image.new("RGB", (20, 10), "white").save(image_path)
    mock_client = mock_client_cls.return_value
    mock_client.upload_blob.return_value = SimpleNamespace(blob=BlobRef(mimeType="image/png", size=1, ref="blob-ref"))
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky("hello", image_path=image_path, image_alt="First page")

    mock_client.upload_blob.assert_called_once_with(image_path.read_bytes())
    _, kwargs = mock_client.send_post.call_args
    assert kwargs["embed"].images[0].alt == "First page"
    assert kwargs["embed"].images[0].aspect_ratio.width == 20
    assert kwargs["embed"].images[0].aspect_ratio.height == 10


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sends_one_image_per_post(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    Image.new("RGB", (20, 10), "white").save(image_path)
    mock_client = mock_client_cls.return_value
    mock_client.upload_blob.return_value = SimpleNamespace(blob=BlobRef(mimeType="image/png", size=1, ref="blob-ref"))
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky("hello", image_path=image_path)

    mock_client.upload_blob.assert_called_once()
    _, kwargs = mock_client.send_post.call_args
    assert len(kwargs["embed"].images) == 1


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_rejects_large_images(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    image_path.write_bytes(b"x" * (MAX_IMAGE_BYTES + 1))
    mock_client = mock_client_cls.return_value

    with pytest.raises(ValueError, match="Bluesky image"):
        post_to_bluesky("hello", image_path=image_path)

    mock_client.upload_blob.assert_not_called()
    mock_client.send_post.assert_not_called()


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_does_not_send_text_only_when_image_fails(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    missing_image_path = tmp_path / "missing.png"
    mock_client = mock_client_cls.return_value

    with pytest.raises(OSError, match="No such file or directory"):
        post_to_bluesky("hello", image_path=missing_image_path)

    mock_client.send_post.assert_not_called()


def test_post_to_bluesky_requires_credentials(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    with pytest.raises(ValueError, match="BLUESKY_HANDLE"):
        post_to_bluesky("hello")

    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="BLUESKY_APP_PASSWORD"):
        post_to_bluesky("hello")


def test_post_to_bluesky_rejects_long_text(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
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
