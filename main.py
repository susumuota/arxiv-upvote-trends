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
    build_bluesky_links_reply,
    build_bluesky_paper_alt,
    build_bluesky_paper_post,
    build_bluesky_report_alt,
    build_bluesky_report_post,
    build_bluesky_source_reply,
    build_bluesky_translation_alt,
    build_bluesky_translation_post,
    build_external_embed,
    build_reply_ref,
    build_report_rows,
    capture_arxiv_first_page,
    convert_pdf_to_png,
    extract_alphaxiv_stats,
    extract_hackernews_stats,
    extract_huggingface_stats,
    fetch_link_card,
    format_japanese_translation_text,
    is_arxiv_id,
    load_ranking_history,
    post_to_bluesky,
    prune_deepl_translation_cache,
    render_report_html,
    render_report_pdf,
    render_translation_html,
    restore_dir,
    save_dir,
    search_alphaxiv,
    search_hackernews,
    search_huggingface,
    translate_abstract_to_japanese,
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
_TRANSLATION_DPI = 100
_BLUESKY_POST_WAIT = 1


def _upload_papers_if_configured(source, papers, upload_path):
    if not HF_REPO_ID:
        return
    logger.info("Uploading %s papers to Hugging Face Dataset", source)
    upload_papers(papers, HF_REPO_ID, upload_path)
    logger.info("Uploaded %s papers to Hugging Face Dataset", source)


def _try_post_to_bluesky(label, text, **kwargs):
    try:
        post_result = post_to_bluesky(text, **kwargs)
    except Exception as e:
        logger.warning("Skipping Bluesky %s after %s.", label, type(e).__name__)
        return None
    else:
        logger.info("Posted Bluesky %s: uri=%s cid=%s", label, post_result.uri, post_result.cid)
        return post_result


def _require_bluesky_config() -> None:
    if not os.environ.get("BLUESKY_HANDLE", "").strip():
        raise ValueError("BLUESKY_HANDLE is required")
    if not os.environ.get("BLUESKY_APP_PASSWORD", "").strip():
        raise ValueError("BLUESKY_APP_PASSWORD is required")


def _post_links_reply(row, paper_result, parent):
    reply_ref = build_reply_ref(root=paper_result, parent=parent)
    post_text = build_bluesky_links_reply(row.arxiv_id)
    try:
        card = fetch_link_card(row.arxiv_url)
    except Exception:
        logger.warning("Failed to fetch link card for %s", row.arxiv_url)
        card = None
    reply_embed = build_external_embed(
        row.arxiv_url, card.title if card else row.title, card.description if card else row.abstract
    )
    time.sleep(_BLUESKY_POST_WAIT)
    result = _try_post_to_bluesky(
        f"links reply for {row.arxiv_id}",
        post_text,
        reply_to=reply_ref,
        embed=reply_embed,
        thumb=card.thumb if card else None,
    )
    return result if result is not None else parent


def _post_translation_reply(row, paper_result, parent):
    if not row.abstract.strip():
        return parent
    try:
        translation_sentences = translate_abstract_to_japanese(row.arxiv_id, row.abstract)
        if not translation_sentences:
            return parent
        logger.info("Rendering Japanese abstract translation HTML for %s", row.arxiv_id)
        html_path = render_translation_html(
            row,
            translation_sentences,
            Path(f"reports/{row.arxiv_id}-ja-abstract.html"),
        )
        logger.info("Rendering Japanese abstract translation PDF for %s", row.arxiv_id)
        pdf_path = render_report_pdf(html_path, Path(f"reports/{row.arxiv_id}-ja-abstract.pdf"))
        logger.info("Converting Japanese abstract translation PDF to PNG for %s", row.arxiv_id)
        image_path = convert_pdf_to_png(
            pdf_path,
            Path(f"reports/{row.arxiv_id}-ja-abstract.png"),
            _TRANSLATION_DPI,
            MAX_IMAGE_BYTES,
        )
    except Exception as e:
        logger.warning("Skipping Japanese abstract reply for %s after %s.", row.arxiv_id, type(e).__name__)
        return parent

    reply_ref = build_reply_ref(root=paper_result, parent=parent)
    translated_text = format_japanese_translation_text(translation_sentences)
    post_text = build_bluesky_translation_post(translated_text)
    image_alt = build_bluesky_translation_alt(translated_text)
    time.sleep(_BLUESKY_POST_WAIT)
    result = _try_post_to_bluesky(
        f"Japanese abstract reply for {row.arxiv_id}",
        post_text,
        image_path=image_path,
        image_alt=image_alt,
        reply_to=reply_ref,
    )
    return result if result is not None else parent


def _post_new_papers(report_rows):
    total = len(report_rows)
    posted_arxiv_ids = []
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
        image_alt = build_bluesky_paper_alt(row)
        post_text = build_bluesky_paper_post(row, total=total)
        time.sleep(_BLUESKY_POST_WAIT)
        paper_result = _try_post_to_bluesky(
            f"post for {row.arxiv_id}", post_text, image_path=image_path, image_alt=image_alt
        )
        if paper_result is None:
            continue
        posted_arxiv_ids.append(row.arxiv_id)
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
        parent = _post_links_reply(row, paper_result, parent)
        _post_translation_reply(row, paper_result, parent)
    return posted_arxiv_ids


def _post_report(report_rows):
    logger.info("Rendering report HTML")
    report_html_path = render_report_html(report_rows, "reports/top_n.html")
    logger.info("Rendering report PDF")
    report_pdf_path = render_report_pdf(report_html_path, "reports/top_n.pdf")
    logger.info("Converting report PDF to PNG")
    report_png_path = convert_pdf_to_png(
        report_pdf_path,
        "reports/top_n.png",
        _REPORT_DPI,
        MAX_IMAGE_BYTES,
    )
    logger.info("Saved Top N report to %s", report_png_path)
    report_post_text = build_bluesky_report_post(report_rows, _REPORT_LIMIT)
    report_alt_text = build_bluesky_report_alt(report_rows)
    time.sleep(_BLUESKY_POST_WAIT)
    _try_post_to_bluesky(
        "Top N report",
        report_post_text,
        image_path=report_png_path,
        image_alt=report_alt_text,
        timeout=60,
    )


def _run_pipeline():
    logger.info("Pruning DeepL translation cache")
    prune_deepl_translation_cache()
    logger.info("Pruned DeepL translation cache")

    logger.info("Searching alphaXiv papers")
    ax_papers = search_alphaxiv(_MAX_PAPERS, interval="30+Days", wait=1)
    logger.info("Fetched %s alphaXiv papers", len(ax_papers))
    _upload_papers_if_configured("alphaXiv", ax_papers, "raw/alphaxiv.jsonl")

    logger.info("Searching Hugging Face papers")
    hf_papers = search_huggingface(_MAX_PAPERS, days=_SEARCH_DAYS, wait=1)
    logger.info("Fetched %s Hugging Face papers", len(hf_papers))
    _upload_papers_if_configured("Hugging Face", hf_papers, "raw/huggingface.jsonl")

    logger.info("Searching Hacker News papers")
    hn_papers = search_hackernews(_MAX_PAPERS, days=_SEARCH_DAYS, wait=1)
    logger.info("Fetched %s Hacker News papers", len(hn_papers))
    _upload_papers_if_configured("Hacker News", hn_papers, "raw/hackernews.jsonl")

    ax_stats = [extract_alphaxiv_stats(p) for p in ax_papers]
    hf_stats = [extract_huggingface_stats(p) for p in hf_papers]
    hn_stats = [extract_hackernews_stats(p) for p in hn_papers]
    df_stats = aggregate_stats(ax_stats + hf_stats + hn_stats)
    valid_arxiv_id_mask = df_stats["arxiv_id"].map(is_arxiv_id)
    invalid_arxiv_ids = df_stats.loc[~valid_arxiv_id_mask, "arxiv_id"].to_list()
    if invalid_arxiv_ids:
        logger.info("Skipping %s non-arXiv IDs (first 10): %s", len(invalid_arxiv_ids), invalid_arxiv_ids[:10])
    df_stats = df_stats.loc[valid_arxiv_id_mask].reset_index(drop=True)
    if hn_stats:
        ax_hf_ids = {aid for s in ax_stats + hf_stats for aid in s["arxiv_id"]}
        hn_only_mask = ~df_stats["arxiv_id"].isin(ax_hf_ids)
        hn_only_ids = df_stats.loc[hn_only_mask, "arxiv_id"].to_list()
        if hn_only_ids:
            logger.info("Skipping %s Hacker News-only papers (first 10): %s", len(hn_only_ids), hn_only_ids[:10])
        df_stats = df_stats.loc[~hn_only_mask].reset_index(drop=True)
    logger.info("stats:\n%s", df_stats.head(50))

    now = datetime.now(UTC)
    logger.info("Loading ranking history")
    history = load_ranking_history(now)
    known_ids = {aid for aid, first_seen in history.items() if now - first_seen >= timedelta(hours=_KNOWN_ID_HOURS)}
    logger.info("Building report rows")
    report_rows = build_report_rows(
        df_stats, ax_papers, hf_papers, hn_papers, limit=_REPORT_LIMIT, known_arxiv_ids=known_ids
    )

    posted_arxiv_ids = _post_new_papers(report_rows)
    logger.info("Updating ranking history for %s posted papers: %s", len(posted_arxiv_ids), posted_arxiv_ids)
    update_ranking_history(history, posted_arxiv_ids, now)
    _post_report(report_rows)


def _save_persistent_data():
    logger.info("Saving persistent data to GCS")
    save_dir(GCS_BUCKET, "persistent_data.tar.gz", "./persistent_data")
    logger.info("Saved persistent data to GCS")


def _restore_persistent_data():
    logger.info("Restoring persistent data from GCS")
    restore_dir(GCS_BUCKET, "persistent_data.tar.gz", "./persistent_data")
    logger.info("Restored persistent data from GCS")


def main():
    _require_bluesky_config()

    if GCS_BUCKET:
        _restore_persistent_data()

    try:
        _run_pipeline()
    except Exception:
        logger.exception("Pipeline failed")
        raise
    finally:
        if GCS_BUCKET:
            _save_persistent_data()


if __name__ == "__main__":
    main()
