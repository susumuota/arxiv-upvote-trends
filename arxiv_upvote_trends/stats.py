# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import re

import pandas as pd

_AGGREGATED_COLUMNS = ["arxiv_id", "score", "num_comments", "count", "url"]
# Reference: https://info.arxiv.org/help/arxiv_identifier.html
_NEW_ARXIV_ID_RE = re.compile(
    r"^(?:"
    r"(?:0[7-9](?:0[4-9]|1[0-2])|1[0-4](?:0[1-9]|1[0-2]))\.(?!0000)\d{4}"
    r"|"
    r"(?:1[5-9]|[2-9]\d|0[0-6])(?:0[1-9]|1[0-2])\.(?!00000)\d{5}"
    r")(?:v[1-9]\d*)?$"
)


def is_arxiv_id(arxiv_id: str) -> bool:
    """Return whether a value is a valid arXiv ID."""
    return bool(_NEW_ARXIV_ID_RE.fullmatch(arxiv_id.strip()))


def aggregate_stats(paper_stats: list[dict]) -> pd.DataFrame:
    """Aggregate alphaXiv and Hugging Face scores by arXiv ID."""
    if not paper_stats:
        return pd.DataFrame(columns=_AGGREGATED_COLUMNS)

    df_docs = pd.DataFrame(paper_stats)
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
