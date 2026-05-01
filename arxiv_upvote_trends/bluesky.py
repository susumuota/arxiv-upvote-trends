# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from atproto import Client
from atproto.exceptions import AtProtocolError

from .report import ReportRow

DEFAULT_SERVICE_URL = "https://bsky.social"
MAX_POST_LENGTH = 300
_MIN_TITLE_LENGTH = 12


@dataclass(frozen=True)
class BlueskyPostResult:
    """Bluesky post identifiers returned after a successful post."""

    uri: str
    cid: str


def build_bluesky_post(
    rows: Sequence[ReportRow],
    generated_at: datetime | None = None,
    limit: int = 5,
) -> str:
    """Build a Bluesky post from top report rows within the 300-character limit."""
    generated = generated_at or datetime.now(tz=UTC)
    generated_text = generated.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    selected_rows = list(rows[:limit])

    if not selected_rows:
        return _fit_post(f"arXiv Upvote Trends\nNo papers found.\nGenerated {generated_text}")

    for row_count in range(len(selected_rows), 0, -1):
        visible_rows = selected_rows[:row_count]
        for title_length in range(48, _MIN_TITLE_LENGTH - 1, -4):
            text = _format_post(visible_rows, generated_text, title_length)
            if len(text) <= MAX_POST_LENGTH:
                return text

    return _fit_post(_format_post(selected_rows[:1], generated_text, _MIN_TITLE_LENGTH))


def post_to_bluesky(text: str) -> BlueskyPostResult:
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
        response = client.send_post(text)
    except AtProtocolError as e:
        raise RuntimeError(f"Failed to post to Bluesky: {type(e).__name__}") from None

    return BlueskyPostResult(
        uri=str(getattr(response, "uri", "")),
        cid=str(getattr(response, "cid", "")),
    )


def _format_post(rows: Sequence[ReportRow], generated_text: str, title_length: int) -> str:
    header = f"arXiv Upvote Trends Top {len(rows)}"
    paper_lines = [
        f"{row.rank}. {_truncate(row.title or row.arxiv_id, title_length)} ({row.score:,} pts)" for row in rows
    ]
    top_url = f"Top paper: {rows[0].arxiv_url}" if rows else ""
    parts = [header, *paper_lines, top_url, f"Generated {generated_text}"]
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
