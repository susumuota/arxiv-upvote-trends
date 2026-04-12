# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os

import pandas as pd
from dotenv import load_dotenv

from arxiv_upvote_trends import restore_dir, save_dir, search_alphaxiv, search_huggingface, upload_papers

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

HF_REPO_ID = os.environ.get("HF_REPO_ID", "")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")


def extract_alphaxiv_stats(paper: dict) -> dict:
    """alphaXiv の検索結果から統計情報を抽出する。"""
    arxiv_id = str(paper.get("universal_paper_id") or "")
    return {
        "url": f"https://www.alphaxiv.org/abs/{arxiv_id}",
        "arxiv_id": [arxiv_id],
        "score": int((paper.get("metrics") or {}).get("public_total_votes") or 0),
        "num_comments": 0,
    }


def extract_huggingface_stats(paper: dict) -> dict:
    """Hugging Face の検索結果から統計情報を抽出する。"""
    arxiv_id = str(paper.get("id") or "")
    return {
        "url": f"https://huggingface.co/papers/{arxiv_id}",
        "arxiv_id": [arxiv_id],
        "score": int(paper.get("upvotes") or 0),
        "num_comments": int(paper.get("comments") or 0),
    }


def aggregate_stats(ax_stats: list[dict], hf_stats: list[dict]) -> pd.DataFrame:
    """alphaXiv と Hugging Face のスコアを arXiv ID で集約する。"""
    df_docs = pd.DataFrame(ax_stats + hf_stats)
    return (
        df_docs.explode("arxiv_id")
        .groupby("arxiv_id")
        .agg(
            score=("score", "sum"),
            num_comments=("num_comments", "sum"),
            count=("url", "count"),
            url=("url", pd.Series.to_list),
        )
        .sort_values(by=["score", "num_comments", "count"], ascending=False)
        .reset_index()
    )


def main():
    if GCS_BUCKET:
        restore_dir(GCS_BUCKET, "fallback_cache.tar.gz", "./fallback_cache")

    ax_papers = search_alphaxiv(max_papers=60, interval="30+Days", wait=1)
    logger.info(f"Fetched {len(ax_papers)} papers")
    if HF_REPO_ID:
        upload_papers(ax_papers, HF_REPO_ID, "raw/alphaxiv.jsonl")

    hf_papers = search_huggingface(max_papers=100, days=2, wait=1)
    logger.info(f"Fetched {len(hf_papers)} papers")
    if HF_REPO_ID:
        upload_papers(hf_papers, HF_REPO_ID, "raw/huggingface.jsonl")

    ax_stats = [extract_alphaxiv_stats(p) for p in ax_papers]
    hf_stats = [extract_huggingface_stats(p) for p in hf_papers]

    df_stats = aggregate_stats(ax_stats, hf_stats)

    logger.info(f"stats:\n{df_stats.head(50)}")

    if GCS_BUCKET:
        save_dir(GCS_BUCKET, "fallback_cache.tar.gz", "./fallback_cache")


if __name__ == "__main__":
    main()
