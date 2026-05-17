# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from atproto import Client, models
from atproto.exceptions import AtProtocolError
from atproto_client.request import Request
from atproto_client.utils.text_builder import TextBuilder
from PIL import Image

from .report import ReportRow

DEFAULT_SERVICE_URL = "https://bsky.social"
DEFAULT_TIMEOUT = 30
# https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/post.json
MAX_POST_LENGTH = 300
# https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/images.json
MAX_IMAGE_BYTES = 1_000_000
# TODO: find the official max alt text length in the AT Protocol spec
_MAX_ALT_LENGTH = 2_000
_MIN_TITLE_LENGTH = 12
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlueskyPostResult:
    """Bluesky post identifiers returned after a successful post."""

    uri: str
    cid: str


def build_bluesky_paper_post(row: ReportRow) -> TextBuilder:
    """Build one Bluesky post for a newly ranked paper."""
    for title_length in range(180, _MIN_TITLE_LENGTH - 1, -8):
        text = _format_paper_post(row, title_length)
        if len(text) <= MAX_POST_LENGTH:
            return TextBuilder().text(text)
    return TextBuilder().text(_truncate(_format_paper_post(row, _MIN_TITLE_LENGTH), MAX_POST_LENGTH))


def build_bluesky_report_alt(rows: list[ReportRow]) -> str:
    """Build alt text for the top report image."""
    total = len(rows)
    text = "\n".join(f"{i + 1}/{total} {row.arxiv_url}" for i, row in enumerate(rows))
    return _truncate(text, _MAX_ALT_LENGTH)


def build_bluesky_report_post(rows: list[ReportRow]) -> TextBuilder:
    """Build one Bluesky post for the top report image."""
    tb = TextBuilder()
    if not rows:
        tb.text("arXiv Upvote Trends Top 30\nNo papers found.")
        return tb

    total = len(rows)
    tb.text("arXiv Upvote Trends Top 30\n")
    for i, row in enumerate(rows):
        tb.text("[")
        tb.link(f"{i + 1}/{total}", row.arxiv_url)
        tb.text("]" if i == total - 1 else "] ")
    return tb


def post_to_bluesky(
    text: TextBuilder,
    image_path: Path | None = None,
    image_alt: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> BlueskyPostResult:
    """Post text to Bluesky using an app password."""
    handle = os.environ.get("BLUESKY_HANDLE", "")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD", "")
    service_url = os.environ.get("BLUESKY_SERVICE_URL", "") or DEFAULT_SERVICE_URL

    if not handle:
        raise ValueError("BLUESKY_HANDLE is required")
    if not app_password:
        raise ValueError("BLUESKY_APP_PASSWORD is required")
    plain_text = text.build_text()
    if len(plain_text) > MAX_POST_LENGTH:
        raise ValueError(f"Bluesky post must be {MAX_POST_LENGTH} characters or fewer")

    phase = "login"
    try:
        client = Client(base_url=service_url, request=Request(timeout=timeout))
        logger.info("Logging in to Bluesky as %s via %s (timeout=%ss)", handle, service_url, timeout)
        client.login(login=handle, password=app_password)
        logger.info("Logged in to Bluesky")
        phase = "image upload"
        embed = _build_image_embed(client, image_path, image_alt) if image_path else None
        phase = "post creation"
        logger.info("Sending Bluesky post text_length=%s has_image=%s", len(plain_text), embed is not None)
        response = client.send_post(text, embed=embed) if embed else client.send_post(text)
        logger.info(
            "Sent Bluesky post uri=%s cid=%s",
            str(getattr(response, "uri", "")),
            str(getattr(response, "cid", "")),
        )
    except AtProtocolError as e:
        logger.warning("Failed to post to Bluesky during %s after %s.", phase, type(e).__name__)
        raise RuntimeError(f"Failed to post to Bluesky during {phase}: {type(e).__name__}") from None

    return BlueskyPostResult(
        uri=str(getattr(response, "uri", "")),
        cid=str(getattr(response, "cid", "")),
    )


def _build_image_embed(client: Client, image_path: Path, image_alt: str) -> models.AppBskyEmbedImages.Main:
    image_bytes = image_path.read_bytes()
    logger.info("Preparing Bluesky image %s size=%s bytes", image_path, len(image_bytes))
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"Bluesky image must be {MAX_IMAGE_BYTES} bytes or fewer")
    with Image.open(image_path) as source_image:
        width, height = source_image.size

    logger.info("Uploading Bluesky image %s width=%s height=%s", image_path, width, height)
    blob = client.upload_blob(image_bytes).blob
    logger.info("Uploaded Bluesky image %s", image_path)
    image = models.AppBskyEmbedImages.Image(
        alt=image_alt,
        image=blob,
        aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=width, height=height),
    )
    return models.AppBskyEmbedImages.Main(images=[image])


def _format_paper_post(row: ReportRow, title_length: int) -> str:
    title = _truncate(row.title or row.arxiv_id, title_length)
    parts = [
        "New arXiv Upvote Trends paper",
        f"Rank {row.rank}: {title}",
        f"{row.score:,} pts",
        row.arxiv_url,
    ]
    return "\n".join(part for part in parts if part)


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f"{text[: max_length - 3].rstrip()}..."
