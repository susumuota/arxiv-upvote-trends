# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import pandas as pd

_AGGREGATED_COLUMNS = ["arxiv_id", "score", "num_comments", "count", "url"]


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
