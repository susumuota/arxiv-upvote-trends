# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os

from dotenv import load_dotenv

from arxiv_upvote_trends import (
    aggregate_stats,
    capture_arxiv_first_page,
    extract_alphaxiv_stats,
    extract_huggingface_stats,
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

    ax_papers = search_alphaxiv(max_papers=60, interval="30+Days", wait=1)
    logger.info("Fetched %s papers", len(ax_papers))
    if HF_REPO_ID:
        upload_papers(ax_papers, HF_REPO_ID, "raw/alphaxiv.jsonl")

    hf_papers = search_huggingface(max_papers=100, days=2, wait=1)
    logger.info("Fetched %s papers", len(hf_papers))
    if HF_REPO_ID:
        upload_papers(hf_papers, HF_REPO_ID, "raw/huggingface.jsonl")

    ax_stats = [extract_alphaxiv_stats(p) for p in ax_papers]
    hf_stats = [extract_huggingface_stats(p) for p in hf_papers]

    df_stats = aggregate_stats(ax_stats + hf_stats)

    logger.info("stats:\n%s", df_stats.head(50))

    for i, arxiv_id in enumerate(df_stats["arxiv_id"].head(3), start=1):
        try:
            capture_arxiv_first_page(arxiv_id, f"top{i}.png")
        except Exception:
            logger.exception("Failed to capture first page for %s", arxiv_id)

    if GCS_BUCKET:
        save_dir(GCS_BUCKET, "fallback_cache.tar.gz", "./fallback_cache")


if __name__ == "__main__":
    main()
