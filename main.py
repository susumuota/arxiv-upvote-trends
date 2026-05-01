# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os

from dotenv import load_dotenv

from arxiv_upvote_trends import (
    aggregate_stats,
    build_bluesky_post,
    build_report_rows,
    capture_arxiv_first_page,
    convert_pdf_to_png,
    extract_alphaxiv_stats,
    extract_huggingface_stats,
    is_arxiv_id,
    post_to_bluesky,
    render_report_html,
    render_report_pdf,
    restore_dir,
    save_dir,
    search_alphaxiv,
    search_huggingface,
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


def main():
    if GCS_BUCKET:
        restore_dir(GCS_BUCKET, "fallback_cache.tar.gz", "./fallback_cache")

    ax_papers = search_alphaxiv(max_papers=20, interval="30+Days", wait=1)
    logger.info("Fetched %s papers", len(ax_papers))
    if HF_REPO_ID:
        upload_papers(ax_papers, HF_REPO_ID, "raw/alphaxiv.jsonl")

    hf_papers = search_huggingface(max_papers=20, days=2, wait=1)
    logger.info("Fetched %s papers", len(hf_papers))
    if HF_REPO_ID:
        upload_papers(hf_papers, HF_REPO_ID, "raw/huggingface.jsonl")

    ax_stats = [extract_alphaxiv_stats(p) for p in ax_papers]
    hf_stats = [extract_huggingface_stats(p) for p in hf_papers]

    df_stats = aggregate_stats(ax_stats + hf_stats)
    valid_arxiv_id_mask = df_stats["arxiv_id"].map(is_arxiv_id)
    invalid_arxiv_ids = df_stats.loc[~valid_arxiv_id_mask, "arxiv_id"].to_list()
    if invalid_arxiv_ids:
        logger.info("Skipping non-arXiv IDs: %s", invalid_arxiv_ids[:10])
    df_stats = df_stats.loc[valid_arxiv_id_mask].reset_index(drop=True)

    logger.info("stats:\n%s", df_stats.head(50))

    report_rows = build_report_rows(df_stats, ax_papers, hf_papers, limit=30)
    report_html_path = render_report_html(report_rows, "reports/top30.html")
    report_pdf_path = render_report_pdf(report_html_path, "reports/top30.pdf")
    report_png_path = convert_pdf_to_png(report_pdf_path, "reports/top30.png")
    logger.info("Saved top 30 report to %s", report_png_path)

    if os.environ.get("BLUESKY_HANDLE", ""):
        post_text = build_bluesky_post(report_rows, limit=5)
        # post_to_bluesky reads BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, and BLUESKY_SERVICE_URL internally.
        post_result = post_to_bluesky(post_text)
        logger.info("Posted Bluesky update: uri=%s cid=%s", post_result.uri, post_result.cid)

    for i, arxiv_id in enumerate(df_stats["arxiv_id"].head(3), start=1):
        try:
            capture_arxiv_first_page(arxiv_id, f"top{i}.png")
        except Exception:
            logger.exception("Failed to capture first page for %s", arxiv_id)

    if GCS_BUCKET:
        save_dir(GCS_BUCKET, "fallback_cache.tar.gz", "./fallback_cache")


if __name__ == "__main__":
    main()
