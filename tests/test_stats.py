# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from arxiv_upvote_trends import aggregate_stats, is_arxiv_id


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


def test_is_arxiv_id_accepts_new_style_ids():
    assert is_arxiv_id("0704.0001")
    assert is_arxiv_id("1412.9999")
    assert is_arxiv_id("1501.00001")
    assert is_arxiv_id("2603.10165")
    assert is_arxiv_id("2603.10165v2")


def test_is_arxiv_id_rejects_non_arxiv_ids():
    assert not is_arxiv_id("")
    assert not is_arxiv_id("deepseek-v4")
    assert not is_arxiv_id("arXiv:2603.10165")
    assert not is_arxiv_id("https://arxiv.org/abs/2603.10165")
    assert not is_arxiv_id("alg-geom/9701001")
    assert not is_arxiv_id("hep-th/9901001")
    assert not is_arxiv_id("math.GT/0309136")
    assert not is_arxiv_id("0703.0001")
    assert not is_arxiv_id("0704.0000")
    assert not is_arxiv_id("1412.00001")
    assert not is_arxiv_id("1501.0001")
    assert not is_arxiv_id("2603.10165v0")
