# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from arxiv_upvote_trends import (
    MAX_IMAGE_BYTES,
    aggregate_stats,
    build_bluesky_paper_alt,
    build_bluesky_paper_post,
    build_bluesky_report_alt,
    build_bluesky_report_post,
    build_bluesky_source_reply,
    build_external_embed,
    build_reply_ref,
    build_report_rows,
    capture_arxiv_first_page,
    convert_pdf_to_png,
    extract_alphaxiv_stats,
    extract_huggingface_stats,
    fetch_link_card,
    is_arxiv_id,
    load_ranking_history,
    post_to_bluesky,
    render_report_html,
    render_report_pdf,
    restore_dir,
    save_dir,
    search_alphaxiv,
    search_huggingface,
    update_ranking_history,
    upload_papers,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

HF_REPO_ID = os.environ.get("HF_REPO_ID", "")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")

_MAX_PAPERS = 1000
_SEARCH_DAYS = 30
_REPORT_LIMIT = 30
_KNOWN_ID_HOURS = 24
_REPORT_DPI = 100
_BLUESKY_POST_WAIT = 1


def _search_and_upload(source, search_fn, search_kwargs, upload_path):
    logger.info("Searching %s papers", source)
    papers = search_fn(**search_kwargs)
    logger.info("Fetched %s papers", len(papers))
    if HF_REPO_ID:
        logger.info("Uploading %s papers to Hugging Face Dataset", source)
        upload_papers(papers, HF_REPO_ID, upload_path)
        logger.info("Uploaded %s papers to Hugging Face Dataset", source)
    return papers


def _try_post_to_bluesky(label, text, **kwargs):
    try:
        post_result = post_to_bluesky(text, **kwargs)
    except Exception as e:
        logger.warning("Skipping Bluesky %s after %s.", label, type(e).__name__)
        return None
    else:
        logger.info("Posted Bluesky %s: uri=%s cid=%s", label, post_result.uri, post_result.cid)
        return post_result


def _post_new_papers(report_rows):
    bluesky_handle = os.environ.get("BLUESKY_HANDLE", "")
    total = len(report_rows)
    for row in reversed(report_rows):
        if not row.is_new:
            continue
        try:
            logger.info("Capturing arXiv first page for %s", row.arxiv_id)
            image_path = capture_arxiv_first_page(
                row.arxiv_id,
                Path(f"reports/{row.arxiv_id}.png"),
                max_output_bytes=MAX_IMAGE_BYTES,
            )
        except Exception:
            logger.exception("Failed to capture first page for %s", row.arxiv_id)
            continue
        logger.info("Captured arXiv first page for %s", row.arxiv_id)
        if bluesky_handle:
            image_alt = build_bluesky_paper_alt(row)
            post_text = build_bluesky_paper_post(row, total=total)
            time.sleep(_BLUESKY_POST_WAIT)
            paper_result = _try_post_to_bluesky(
                f"post for {row.arxiv_id}", post_text, image_path=image_path, image_alt=image_alt
            )
            if paper_result is None:
                continue
            sources = sorted(row.sources, key=lambda source: -source.score)
            parent = paper_result
            for i, source in enumerate(sources):
                try:
                    card = fetch_link_card(source.url)
                except Exception:
                    logger.warning("Failed to fetch link card for %s", source.url)
                    card = None
                reply_text = build_bluesky_source_reply(
                    source.label,
                    source.url,
                    source.score,
                    source.num_comments,
                    i + 1,
                    len(sources),
                    published_at=source.published_at,
                )
                reply_embed = build_external_embed(
                    source.url, card.title if card else source.label, card.description if card else row.title
                )
                reply_ref = build_reply_ref(root=paper_result, parent=parent)
                time.sleep(_BLUESKY_POST_WAIT)
                result = _try_post_to_bluesky(
                    f"{source.label} reply for {row.arxiv_id}",
                    reply_text,
                    reply_to=reply_ref,
                    embed=reply_embed,
                    thumb=card.thumb if card else None,
                )
                if result is not None:
                    parent = result


def _post_report(report_rows):
    logger.info("Rendering report HTML")
    report_html_path = render_report_html(report_rows, "reports/top30.html")
    logger.info("Rendering report PDF")
    report_pdf_path = render_report_pdf(report_html_path, "reports/top30.pdf")
    logger.info("Converting report PDF to PNG")
    report_png_path = convert_pdf_to_png(
        report_pdf_path,
        "reports/top30.png",
        _REPORT_DPI,
        MAX_IMAGE_BYTES,
    )
    logger.info("Saved top 30 report to %s", report_png_path)
    if os.environ.get("BLUESKY_HANDLE", ""):
        report_post_text = build_bluesky_report_post(report_rows)
        report_alt_text = build_bluesky_report_alt(report_rows)
        time.sleep(_BLUESKY_POST_WAIT)
        _try_post_to_bluesky(
            "top 30 report",
            report_post_text,
            image_path=report_png_path,
            image_alt=report_alt_text,
            timeout=60,
        )


def main():
    if GCS_BUCKET:
        logger.info("Restoring persistent data from GCS")
        restore_dir(GCS_BUCKET, "persistent_data.tar.gz", "./persistent_data")
        logger.info("Restored persistent data from GCS")

    ax_papers = _search_and_upload(
        "alphaXiv",
        search_alphaxiv,
        {"max_papers": _MAX_PAPERS, "interval": "30+Days", "wait": 1},
        "raw/alphaxiv.jsonl",
    )
    hf_papers = _search_and_upload(
        "Hugging Face",
        search_huggingface,
        {"max_papers": _MAX_PAPERS, "days": _SEARCH_DAYS, "wait": 1},
        "raw/huggingface.jsonl",
    )

    ax_stats = [extract_alphaxiv_stats(p) for p in ax_papers]
    hf_stats = [extract_huggingface_stats(p) for p in hf_papers]
    df_stats = aggregate_stats(ax_stats + hf_stats)
    valid_arxiv_id_mask = df_stats["arxiv_id"].map(is_arxiv_id)
    invalid_arxiv_ids = df_stats.loc[~valid_arxiv_id_mask, "arxiv_id"].to_list()
    if invalid_arxiv_ids:
        logger.info("Skipping non-arXiv IDs: %s", invalid_arxiv_ids[:10])
    df_stats = df_stats.loc[valid_arxiv_id_mask].reset_index(drop=True)
    logger.info("stats:\n%s", df_stats.head(50))

    now = datetime.now(UTC)
    logger.info("Loading ranking history")
    history = load_ranking_history(now)
    known_ids = {aid for aid, first_seen in history.items() if now - first_seen >= timedelta(hours=_KNOWN_ID_HOURS)}
    logger.info("Building report rows")
    report_rows = build_report_rows(df_stats, ax_papers, hf_papers, limit=_REPORT_LIMIT, known_arxiv_ids=known_ids)
    logger.info("Updating ranking history")
    update_ranking_history(history, [row.arxiv_id for row in report_rows], now)

    _post_new_papers(report_rows)
    _post_report(report_rows)

    if GCS_BUCKET:
        logger.info("Saving persistent data to GCS")
        save_dir(GCS_BUCKET, "persistent_data.tar.gz", "./persistent_data")
        logger.info("Saved persistent data to GCS")


if __name__ == "__main__":
    main()
