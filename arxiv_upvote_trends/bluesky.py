# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import os
from dataclasses import dataclass
from pathlib import Path

from atproto import Client, models
from atproto.exceptions import AtProtocolError
from PIL import Image

from .report import ReportRow

DEFAULT_SERVICE_URL = "https://bsky.social"
MAX_POST_LENGTH = 300
MAX_IMAGE_BYTES = 1_000_000
_MIN_TITLE_LENGTH = 12


@dataclass(frozen=True)
class BlueskyPostResult:
    """Bluesky post identifiers returned after a successful post."""

    uri: str
    cid: str


def build_bluesky_paper_post(row: ReportRow) -> str:
    """Build one Bluesky post for a newly ranked paper."""
    for title_length in range(180, _MIN_TITLE_LENGTH - 1, -8):
        text = _format_paper_post(row, title_length)
        if len(text) <= MAX_POST_LENGTH:
            return text
    return _fit_post(_format_paper_post(row, _MIN_TITLE_LENGTH))


def build_bluesky_report_post(rows: list[ReportRow]) -> str:
    """Build one Bluesky post for the top report image."""
    if not rows:
        return "arXiv Upvote Trends Top 30\nNo papers found."

    total_score = sum(row.score for row in rows)
    total_comments = sum(row.num_comments for row in rows)
    parts = [
        "arXiv Upvote Trends Top 30",
        f"{len(rows):,} papers · total upvotes {total_score:,} · comments {total_comments:,}",
        f"Top paper: {rows[0].arxiv_url}",
    ]
    return _fit_post("\n".join(parts))


def post_to_bluesky(
    text: str,
    image_path: str | Path | None = None,
    image_alt: str = "",
) -> BlueskyPostResult:
    """Post text to Bluesky using an app password."""
    handle = os.environ.get("BLUESKY_HANDLE", "")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD", "")
    service_url = os.environ.get("BLUESKY_SERVICE_URL", "") or DEFAULT_SERVICE_URL

    if not handle:
        raise ValueError("BLUESKY_HANDLE is required")
    if not app_password:
        raise ValueError("BLUESKY_APP_PASSWORD is required")
    if len(text) > MAX_POST_LENGTH:
        raise ValueError(f"Bluesky post must be {MAX_POST_LENGTH} characters or fewer")

    try:
        client = Client(base_url=service_url)
        client.login(login=handle, password=app_password)
        embed = _build_image_embed(client, Path(image_path), image_alt) if image_path else None
        response = client.send_post(text, embed=embed) if embed else client.send_post(text)
    except AtProtocolError as e:
        raise RuntimeError(f"Failed to post to Bluesky: {type(e).__name__}") from None

    return BlueskyPostResult(
        uri=str(getattr(response, "uri", "")),
        cid=str(getattr(response, "cid", "")),
    )


def _build_image_embed(client: Client, image_path: Path, image_alt: str) -> models.AppBskyEmbedImages.Main:
    image_bytes = image_path.read_bytes()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"Bluesky image must be {MAX_IMAGE_BYTES} bytes or fewer")
    with Image.open(image_path) as source_image:
        width, height = source_image.size

    blob = client.upload_blob(image_bytes).blob
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
    clean_text = " ".join(text.split())
    if len(clean_text) <= max_length:
        return clean_text
    if max_length <= 3:
        return clean_text[:max_length]
    return f"{clean_text[: max_length - 3].rstrip()}..."


def _fit_post(text: str) -> str:
    if len(text) <= MAX_POST_LENGTH:
        return text
    return _truncate(text, MAX_POST_LENGTH)
