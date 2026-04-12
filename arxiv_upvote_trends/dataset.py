# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import io
import json
import logging

from datasets import load_dataset
from huggingface_hub import HfApi

logger = logging.getLogger(__name__)


def upload_papers(papers: list[dict], repo_id: str, filename: str) -> str:
    """Save papers as JSONL and upload to a Hugging Face Dataset repo.

    Args:
        papers: List of paper dicts from search_alphaxiv.
        repo_id: Hugging Face dataset repo ID (e.g. "username/arxiv-upvote-trends").
        filename: Name of the JSONL file in the repo.

    Returns:
        URL of the dataset repo.
    """
    api = HfApi()

    with io.BytesIO() as buf:
        for paper in papers:
            buf.write((json.dumps(paper, ensure_ascii=False, default=str) + "\n").encode())
        buf.seek(0)
        api.upload_file(
            path_or_fileobj=buf,
            path_in_repo=filename,
            repo_id=repo_id,
            repo_type="dataset",
        )

    url = f"https://huggingface.co/datasets/{repo_id}"
    logger.info(f"Uploaded {len(papers)} papers to {url}")
    return url


def download_papers(repo_id: str, filename) -> list[dict]:
    """Download papers from a Hugging Face Dataset repo.

    Args:
        repo_id: Hugging Face dataset repo ID (e.g. "username/arxiv-upvote-trends").
        filename: Name of the JSONL file in the repo.

    Returns:
        List of paper dicts.
    """
    ds = load_dataset(repo_id, data_files=filename)
    return [dict(row) for row in ds["train"]]
