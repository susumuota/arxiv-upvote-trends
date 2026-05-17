# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from types import SimpleNamespace
from unittest.mock import ANY, patch

import pytest
from atproto import models
from atproto.exceptions import AtProtocolError
from atproto_client.models.blob_ref import BlobRef
from atproto_client.utils.text_builder import TextBuilder
from PIL import Image

from arxiv_upvote_trends.bluesky import (
    DEFAULT_TIMEOUT,
    MAX_IMAGE_BYTES,
    MAX_POST_LENGTH,
    BlueskyPostResult,
    build_bluesky_paper_alt,
    build_bluesky_paper_post,
    build_bluesky_report_post,
    build_bluesky_source_reply,
    build_reply_ref,
    post_to_bluesky,
)
from arxiv_upvote_trends.report import ReportRow


def test_build_bluesky_paper_post_includes_row_details_and_url():
    row = _row(rank=2, arxiv_id="2604.00002", title="Second paper", score=45)

    result = build_bluesky_paper_post(row, 10)

    assert isinstance(result, TextBuilder)
    text = result.build_text()
    assert len(text) <= MAX_POST_LENGTH
    assert "[2/10]" in text
    assert "45 Upvotes" in text
    assert "0 Comments" in text
    assert "1 Posts" in text
    assert "2604.00002" in text
    assert "Second paper" in text
    facets = result.build_facets()
    assert len(facets) == 1
    link = facets[0].features[0]
    assert isinstance(link, models.AppBskyRichtextFacet.Link)
    assert link.uri == "https://arxiv.org/abs/2604.00002"


def test_build_bluesky_paper_post_truncates_long_titles():
    row = _row(
        rank=1,
        arxiv_id="2604.00001",
        title="A very long paper title that should be shortened before posting to Bluesky " * 20,
        score=123,
    )

    result = build_bluesky_paper_post(row, 10)

    text = result.build_text()
    assert len(text) <= MAX_POST_LENGTH
    assert "..." in text
    assert "2604.00001" in text


def test_build_bluesky_paper_post_includes_authors():
    row = _row(rank=1, arxiv_id="2604.00001", title="Paper", score=10, authors="Alice, Bob")

    result = build_bluesky_paper_post(row, 5)

    text = result.build_text()
    assert "Alice, Bob" in text


def test_build_bluesky_paper_post_shows_new_emoji_only_when_new():
    row_new = _row(rank=1, arxiv_id="2604.00001", title="Paper", score=10, is_new=True)
    row_old = _row(rank=1, arxiv_id="2604.00001", title="Paper", score=10, is_new=False)

    assert "🆕" in build_bluesky_paper_post(row_new, 5).build_text()
    assert "🆕" not in build_bluesky_paper_post(row_old, 5).build_text()


def test_build_bluesky_report_post_includes_linked_indices():
    rows = [
        _row(rank=1, arxiv_id="2604.00001", title="First paper", score=123),
        _row(rank=2, arxiv_id="2604.00002", title="Second paper", score=45),
    ]

    result = build_bluesky_report_post(rows)

    assert isinstance(result, TextBuilder)
    text = result.build_text()
    assert len(text) <= MAX_POST_LENGTH
    assert "arXiv Upvote Trends Top 30" in text
    assert "[1/2]" in text
    assert "[2/2]" in text
    facets = result.build_facets()
    assert len(facets) == 2
    link0 = facets[0].features[0]
    link1 = facets[1].features[0]
    assert isinstance(link0, models.AppBskyRichtextFacet.Link)
    assert isinstance(link1, models.AppBskyRichtextFacet.Link)
    assert link0.uri == "https://arxiv.org/abs/2604.00001"
    assert link1.uri == "https://arxiv.org/abs/2604.00002"


def test_build_bluesky_report_post_handles_empty_rows():
    result = build_bluesky_report_post([])
    assert isinstance(result, TextBuilder)
    assert result.build_text() == "arXiv Upvote Trends Top 30\nNo papers found."


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_logs_in_and_sends_post(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    result = post_to_bluesky(TextBuilder().text("hello"))

    mock_client_cls.assert_called_once_with(base_url="https://bsky.social", request=ANY)
    mock_client.login.assert_called_once_with(login="user.bsky.social", password="app-password")
    mock_client.send_post.assert_called_once()
    assert mock_client.send_post.call_args.args[0].build_text() == "hello"
    assert result.uri == "at://did/example"
    assert result.cid == "cid-value"


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_uses_configured_service_url(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    monkeypatch.setenv("BLUESKY_SERVICE_URL", "https://example.test")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"))

    mock_client_cls.assert_called_once_with(base_url="https://example.test", request=ANY)


@patch("arxiv_upvote_trends.bluesky.Request")
@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_passes_timeout_to_request(mock_client_cls, mock_request_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"), timeout=60)

    mock_request_cls.assert_called_once_with(timeout=60)
    mock_client_cls.assert_called_once_with(base_url="https://bsky.social", request=mock_request_cls.return_value)


@patch("arxiv_upvote_trends.bluesky.Request")
@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_uses_default_timeout(mock_client_cls, mock_request_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"))

    mock_request_cls.assert_called_once_with(timeout=DEFAULT_TIMEOUT)


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_attaches_images(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    Image.new("RGB", (20, 10), "white").save(image_path)
    mock_client = mock_client_cls.return_value
    mock_client.upload_blob.return_value = SimpleNamespace(blob=BlobRef(mimeType="image/png", size=1, ref="blob-ref"))
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"), image_path=image_path, image_alt="First page")

    mock_client.upload_blob.assert_called_once_with(image_path.read_bytes())
    _, kwargs = mock_client.send_post.call_args
    assert kwargs["embed"].images[0].alt == "First page"
    assert kwargs["embed"].images[0].aspect_ratio.width == 20
    assert kwargs["embed"].images[0].aspect_ratio.height == 10


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_logs_image_upload_and_post_creation(mock_client_cls, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    Image.new("RGB", (20, 10), "white").save(image_path)
    mock_client = mock_client_cls.return_value
    mock_client.upload_blob.return_value = SimpleNamespace(blob=BlobRef(mimeType="image/png", size=1, ref="blob-ref"))
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    with caplog.at_level("INFO"):
        post_to_bluesky(TextBuilder().text("hello"), image_path=image_path, image_alt="First page")

    assert "Logging in to Bluesky as user.bsky.social via https://bsky.social" in caplog.text
    assert f"Preparing Bluesky image {image_path}" in caplog.text
    assert f"Uploading Bluesky image {image_path} width=20 height=10" in caplog.text
    assert f"Uploaded Bluesky image {image_path}" in caplog.text
    assert "Sending Bluesky post text_length=5 has_image=True" in caplog.text
    assert "Sent Bluesky post uri=at://did/example cid=cid-value" in caplog.text


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sends_one_image_per_post(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    image_path = tmp_path / "2604.00001.png"
    Image.new("RGB", (20, 10), "white").save(image_path)
    mock_client = mock_client_cls.return_value
    mock_client.upload_blob.return_value = SimpleNamespace(blob=BlobRef(mimeType="image/png", size=1, ref="blob-ref"))
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"), image_path=image_path)

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
        post_to_bluesky(TextBuilder().text("hello"), image_path=image_path)

    mock_client.upload_blob.assert_not_called()
    mock_client.send_post.assert_not_called()


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_does_not_send_text_only_when_image_fails(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    missing_image_path = tmp_path / "missing.png"
    mock_client = mock_client_cls.return_value

    with pytest.raises(OSError, match="No such file or directory"):
        post_to_bluesky(TextBuilder().text("hello"), image_path=missing_image_path)

    mock_client.send_post.assert_not_called()


def test_post_to_bluesky_requires_credentials(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    with pytest.raises(ValueError, match="BLUESKY_HANDLE"):
        post_to_bluesky(TextBuilder().text("hello"))

    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="BLUESKY_APP_PASSWORD"):
        post_to_bluesky(TextBuilder().text("hello"))


def test_post_to_bluesky_rejects_long_text(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    with pytest.raises(ValueError, match="300"):
        post_to_bluesky(TextBuilder().text("x" * 301))


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sanitizes_atproto_errors(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.login.side_effect = AtProtocolError("request failed with app-password")

    with pytest.raises(RuntimeError) as exc_info:
        post_to_bluesky(TextBuilder().text("hello"))

    assert str(exc_info.value) == "Failed to post to Bluesky during login: AtProtocolError"
    assert "app-password" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_sanitizes_send_post_errors(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.side_effect = AtProtocolError("post failed with app-password")

    with pytest.raises(RuntimeError) as exc_info:
        post_to_bluesky(TextBuilder().text("hello"))

    assert str(exc_info.value) == "Failed to post to Bluesky during post creation: AtProtocolError"
    assert "app-password" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def _row(
    rank: int,
    arxiv_id: str,
    title: str,
    score: int,
    *,
    authors: str = "",
    abstract: str = "",
    is_new: bool = True,
) -> ReportRow:
    return ReportRow(
        rank=rank,
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
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
        abstract=abstract,
        is_new=is_new,
    )


def test_build_bluesky_paper_alt_uses_abstract():
    row = _row(rank=1, arxiv_id="2604.00001", title="Title", score=10, abstract="This paper proposes a method.")

    assert build_bluesky_paper_alt(row) == "This paper proposes a method."


def test_build_bluesky_paper_alt_falls_back_to_title():
    row = _row(rank=1, arxiv_id="2604.00001", title="Some title", score=10)

    assert build_bluesky_paper_alt(row) == "First page of arXiv:2604.00001: Some title"


def test_build_bluesky_paper_alt_truncates_long_abstract():
    row = _row(rank=1, arxiv_id="2604.00001", title="Title", score=10, abstract="x" * 3000)

    result = build_bluesky_paper_alt(row)

    assert len(result) <= 2000
    assert result.endswith("...")


def test_build_bluesky_source_reply_includes_stats_and_link():
    result = build_bluesky_source_reply("Hugging Face", "https://huggingface.co/papers/2604.00001", 5, 3, 1, 2)

    assert isinstance(result, TextBuilder)
    text = result.build_text()
    assert "(1/2)" in text
    assert "5 Upvotes" in text
    assert "3 Comments" in text
    assert "Hugging Face" in text
    facets = result.build_facets()
    assert len(facets) == 1
    link = facets[0].features[0]
    assert isinstance(link, models.AppBskyRichtextFacet.Link)
    assert link.uri == "https://huggingface.co/papers/2604.00001"


def test_build_bluesky_source_reply_with_zero_comments():
    result = build_bluesky_source_reply("alphaXiv", "https://www.alphaxiv.org/abs/2604.00001", 12, 0, 2, 2)

    text = result.build_text()
    assert "(2/2)" in text
    assert "12 Upvotes" in text
    assert "0 Comments" in text
    assert "alphaXiv" in text


def test_build_reply_ref_creates_correct_refs():
    root = BlueskyPostResult(uri="at://did/root", cid="cid-root")
    parent = BlueskyPostResult(uri="at://did/parent", cid="cid-parent")

    ref = build_reply_ref(root, parent)

    assert isinstance(ref, models.AppBskyFeedPost.ReplyRef)
    assert ref.root.uri == "at://did/root"
    assert ref.root.cid == "cid-root"
    assert ref.parent.uri == "at://did/parent"
    assert ref.parent.cid == "cid-parent"


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_passes_reply_to(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/reply", cid="cid-reply")
    reply_ref = models.AppBskyFeedPost.ReplyRef(
        root=models.ComAtprotoRepoStrongRef.Main(uri="at://did/root", cid="cid-root"),
        parent=models.ComAtprotoRepoStrongRef.Main(uri="at://did/parent", cid="cid-parent"),
    )

    post_to_bluesky(TextBuilder().text("reply"), reply_to=reply_ref)

    _, kwargs = mock_client.send_post.call_args
    assert kwargs["reply_to"] is reply_ref


@patch("arxiv_upvote_trends.bluesky.Client")
def test_post_to_bluesky_passes_none_reply_to_by_default(mock_client_cls, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")
    mock_client = mock_client_cls.return_value
    mock_client.send_post.return_value = SimpleNamespace(uri="at://did/example", cid="cid-value")

    post_to_bluesky(TextBuilder().text("hello"))

    _, kwargs = mock_client.send_post.call_args
    assert kwargs["reply_to"] is None
