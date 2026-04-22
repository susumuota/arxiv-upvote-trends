# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from arxiv_upvote_trends import aggregate_stats


def test_aggregate_stats_combines_sources_by_arxiv_id():
    paper_stats = [
        {
            "url": "https://www.alphaxiv.org/abs/2604.00001",
            "arxiv_id": ["2604.00001"],
            "score": 4,
            "num_comments": 0,
        },
        {
            "url": "https://huggingface.co/papers/2604.00001",
            "arxiv_id": ["2604.00001"],
            "score": 7,
            "num_comments": 2,
        },
        {
            "url": "https://huggingface.co/papers/2604.00002",
            "arxiv_id": ["2604.00002"],
            "score": 5,
            "num_comments": 3,
        },
    ]

    result = aggregate_stats(paper_stats)

    assert result.to_dict("records") == [
        {
            "arxiv_id": "2604.00001",
            "score": 11,
            "num_comments": 2,
            "count": 2,
            "url": [
                "https://www.alphaxiv.org/abs/2604.00001",
                "https://huggingface.co/papers/2604.00001",
            ],
        },
        {
            "arxiv_id": "2604.00002",
            "score": 5,
            "num_comments": 3,
            "count": 1,
            "url": ["https://huggingface.co/papers/2604.00002"],
        },
    ]


def test_aggregate_stats_sorts_by_score_comments_and_count():
    paper_stats = [
        {"url": "a", "arxiv_id": ["paper-a"], "score": 10, "num_comments": 1},
        {"url": "b", "arxiv_id": ["paper-b"], "score": 10, "num_comments": 2},
        {"url": "c", "arxiv_id": ["paper-c"], "score": 9, "num_comments": 5},
        {"url": "d", "arxiv_id": ["paper-a"], "score": 0, "num_comments": 1},
    ]

    result = aggregate_stats(paper_stats)

    assert result["arxiv_id"].to_list() == ["paper-a", "paper-b", "paper-c"]


def test_aggregate_stats_returns_empty_frame_for_empty_input():
    result = aggregate_stats([])

    assert result.empty
    assert result.columns.to_list() == ["arxiv_id", "score", "num_comments", "count", "url"]
