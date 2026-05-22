# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
from atproto import Client, models
from atproto.exceptions import AtProtocolError
from atproto_client.request import Request
from atproto_client.utils.text_builder import TextBuilder
from PIL import Image

from .report import ReportRow

_CARDYB_URL = "https://cardyb.bsky.app/v1/extract"
DEFAULT_SERVICE_URL = "https://bsky.social"
DEFAULT_TIMEOUT = 30
# https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/post.json
MAX_POST_LENGTH = 300
# https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/embed/images.json
MAX_IMAGE_BYTES = 1_000_000
# TODO: find the official max alt text length in the AT Protocol spec
_MAX_ALT_LENGTH = 2_000
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlueskyPostResult:
    """Bluesky post identifiers returned after a successful post."""

    uri: str
    cid: str


@dataclass(frozen=True)
class LinkCard:
    """Link card metadata fetched from Bluesky's card service."""

    title: str
    description: str
    thumb: bytes | None


def fetch_link_card(url: str, timeout: int = DEFAULT_TIMEOUT) -> LinkCard:
    """Fetch link card metadata and thumbnail from Bluesky's card service."""
    resp = requests.get(_CARDYB_URL, params={"url": url}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", "")
    description = data.get("description", "")
    thumb = None
    image_url = data.get("image", "")
    if image_url:
        img_resp = requests.get(image_url, timeout=timeout)
        img_resp.raise_for_status()
        thumb = img_resp.content
    return LinkCard(title=title, description=description, thumb=thumb)


def build_bluesky_paper_post(row: ReportRow, total: int) -> TextBuilder:
    """Build one Bluesky post for a newly ranked paper."""
    header = f"[{row.rank}/{total}] {row.score} Upvotes, {row.num_comments} Comments, {row.count} Posts"
    new_prefix = "🆕" if row.is_new else ""
    title = row.title or row.arxiv_id
    authors = row.authors or ""

    body = f"{new_prefix}{title}"
    if authors:
        body += f"\n\n{authors}"

    tb = TextBuilder()
    tb.text(f"{header}, ")
    tb.link(f"arXiv:{row.arxiv_id}", row.arxiv_url)
    tb.text("\n\n")
    remaining = MAX_POST_LENGTH - len(tb.build_text())
    tb.text(_truncate(body, remaining))
    return tb


def build_bluesky_report_alt(rows: list[ReportRow]) -> str:
    """Build alt text for the top report image."""
    total = len(rows)
    text = "\n".join(f"{i + 1}/{total} {row.arxiv_url}" for i, row in enumerate(rows))
    return _truncate(text, _MAX_ALT_LENGTH)


def build_bluesky_paper_alt(row: ReportRow) -> str:
    """Build alt text for a paper first-page image."""
    if row.abstract:
        return _truncate(row.abstract, _MAX_ALT_LENGTH)
    title = row.title or row.arxiv_id
    return _truncate(f"First page of arXiv:{row.arxiv_id}: {title}", _MAX_ALT_LENGTH)


def build_bluesky_translation_post(translated_abstract: str) -> TextBuilder:
    """Build a Bluesky reply post from a Japanese abstract translation."""
    tb = TextBuilder()
    tb.text(_truncate(translated_abstract, MAX_POST_LENGTH))
    return tb


def build_bluesky_translation_alt(translated_abstract: str) -> str:
    """Build alt text from a Japanese abstract translation."""
    return _truncate(translated_abstract, _MAX_ALT_LENGTH)


def build_bluesky_report_post(rows: list[ReportRow], limit: int) -> TextBuilder:
    """Build one Bluesky post for the top report image."""
    tb = TextBuilder()
    if not rows:
        tb.text(f"arXiv Upvote Trends Top {limit}\nNo papers found.")
        return tb

    total = len(rows)
    tb.text(f"arXiv Upvote Trends Top {limit}\n")
    for i, row in enumerate(rows):
        tb.text("[")
        tb.link(f"{i + 1}/{total}", row.arxiv_url)
        tb.text("]" if i == total - 1 else "] ")
    return tb


def build_bluesky_source_reply(
    label: str,
    url: str,
    score: int,
    num_comments: int,
    index: int,
    total: int,
    published_at: datetime | None = None,
) -> TextBuilder:
    """Build a Bluesky reply post linking to a source discussion page."""
    tb = TextBuilder()
    date_part = f", {published_at.strftime('%d %b %Y')}" if published_at else ""
    tb.text(f"({index}/{total}) {score} Upvotes, {num_comments} Comments{date_part}, ")
    tb.link(label, url)
    return tb


def build_bluesky_links_reply(arxiv_id: str) -> TextBuilder:
    """Build a Bluesky reply post with paper links and platform search links."""
    tb = TextBuilder()
    tb.text("Links: ")
    tb.link("abs", f"https://arxiv.org/abs/{arxiv_id}")
    tb.text(", ")
    tb.link("pdf", f"https://arxiv.org/pdf/{arxiv_id}.pdf")
    tb.text("\nSearch: ")
    tb.link("Bluesky", f"https://bsky.app/search?q=%22{arxiv_id}%22")
    tb.text(", ")
    tb.link("Twitter", f"https://x.com/search?q=%22{arxiv_id}%22")
    tb.text(", ")
    tb.link("Reddit", f"https://www.reddit.com/search/?q=%22{arxiv_id}%22")
    tb.text(", ")
    tb.link("Hacker News", f"https://hn.algolia.com/?query=%22{arxiv_id}%22")
    tb.text(", ")
    tb.link("Hugging Face", f"https://huggingface.co/papers/{arxiv_id}")
    tb.text(", ")
    tb.link("alphaXiv", f"https://www.alphaxiv.org/abs/{arxiv_id}")
    return tb


def build_external_embed(uri: str, title: str, description: str) -> models.AppBskyEmbedExternal.Main:
    """Build an external link card embed."""
    return models.AppBskyEmbedExternal.Main(
        external=models.AppBskyEmbedExternal.External(uri=uri, title=title, description=description)
    )


def build_reply_ref(root: BlueskyPostResult, parent: BlueskyPostResult) -> models.AppBskyFeedPost.ReplyRef:
    """Build a ReplyRef for threading a reply under a root post."""
    root_ref = models.ComAtprotoRepoStrongRef.Main(uri=root.uri, cid=root.cid)
    parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=parent.uri, cid=parent.cid)
    return models.AppBskyFeedPost.ReplyRef(root=root_ref, parent=parent_ref)


def post_to_bluesky(
    text: TextBuilder,
    image_path: Path | None = None,
    image_alt: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    reply_to: models.AppBskyFeedPost.ReplyRef | None = None,
    embed: models.AppBskyEmbedImages.Main | models.AppBskyEmbedExternal.Main | None = None,
    thumb: bytes | None = None,
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
        if image_path:
            embed = _build_image_embed(client, image_path, image_alt)
        elif isinstance(embed, models.AppBskyEmbedExternal.Main) and thumb:
            blob = client.upload_blob(thumb).blob
            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    uri=embed.external.uri,
                    title=embed.external.title,
                    description=embed.external.description,
                    thumb=blob,
                )
            )
        phase = "post creation"
        logger.info("Sending Bluesky post text_length=%s has_image=%s", len(plain_text), embed is not None)
        response = client.send_post(text, reply_to=reply_to, embed=embed)
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


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f"{text[: max_length - 3].rstrip()}..."
