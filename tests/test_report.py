# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
from PIL import Image

from arxiv_upvote_trends.report import (
    ReportRow,
    build_report_rows,
    convert_pdf_to_png,
    render_report_html,
    report_html,
)


def test_build_report_rows_combines_stats_with_source_papers():
    df_stats = pd.DataFrame(
        [
            {
                "arxiv_id": "2604.00001",
                "score": 17,
                "num_comments": 2,
                "count": 2,
                "url": [
                    "https://www.alphaxiv.org/abs/2604.00001",
                    "https://huggingface.co/papers/2604.00001",
                ],
            },
            {
                "arxiv_id": "2604.00002",
                "score": 4,
                "num_comments": 0,
                "count": 1,
                "url": ["https://www.alphaxiv.org/abs/2604.00002"],
            },
        ]
    )
    ax_papers = [
        {
            "universal_paper_id": "2604.00001",
            "title": "alphaXiv title",
            "metrics": {"public_total_votes": 10},
        },
        {
            "universal_paper_id": "2604.00002",
            "title": "alphaXiv only title",
            "metrics": {"public_total_votes": 4},
        },
    ]
    hf_papers = [
        {
            "id": "2604.00001",
            "title": "Hugging Face title",
            "authors": [{"name": "Ada"}, {"name": "Grace"}],
            "upvotes": 7,
            "comments": 2,
        }
    ]

    rows = build_report_rows(df_stats, ax_papers, hf_papers, limit=30)

    assert rows == [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="Hugging Face title",
            authors="Ada, Grace",
            score=17,
            num_comments=2,
            count=2,
            alphaxiv_score=10,
            huggingface_score=7,
            huggingface_comments=2,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="https://www.alphaxiv.org/abs/2604.00001",
            huggingface_url="https://huggingface.co/papers/2604.00001",
            source_urls=(
                "https://www.alphaxiv.org/abs/2604.00001",
                "https://huggingface.co/papers/2604.00001",
            ),
        ),
        ReportRow(
            rank=2,
            arxiv_id="2604.00002",
            title="alphaXiv only title",
            authors="",
            score=4,
            num_comments=0,
            count=1,
            alphaxiv_score=4,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00002",
            alphaxiv_url="https://www.alphaxiv.org/abs/2604.00002",
            huggingface_url="https://huggingface.co/papers/2604.00002",
            source_urls=("https://www.alphaxiv.org/abs/2604.00002",),
        ),
    ]


def test_build_report_rows_respects_limit():
    df_stats = pd.DataFrame(
        [
            {"arxiv_id": f"2604.{index:05}", "score": index, "num_comments": 0, "count": 1, "url": []}
            for index in range(3)
        ]
    )

    rows = build_report_rows(df_stats, [], [], limit=2)

    assert [row.arxiv_id for row in rows] == ["2604.00000", "2604.00001"]


def test_report_html_escapes_paper_fields():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="<script>alert(1)</script>",
            authors="A & B",
            score=1,
            num_comments=0,
            count=1,
            alphaxiv_score=1,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
        )
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "A &amp; B" in html
    assert "<script>alert(1)</script>" not in html


def test_render_report_html_writes_file(tmp_path):
    output_path = tmp_path / "top30.html"

    result = render_report_html([], output_path, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert result == output_path
    assert "arXiv Upvote Trends Top 0" in output_path.read_text(encoding="utf-8")


def test_convert_pdf_to_png_combines_multiple_pages(tmp_path):
    output_path = tmp_path / "report.png"
    images = [
        Image.new("RGB", (20, 10), "white"),
        Image.new("RGB", (10, 12), "white"),
    ]

    with patch("arxiv_upvote_trends.report.convert_from_path", return_value=images):
        result = convert_pdf_to_png("report.pdf", output_path, dpi=90)

    assert result == output_path
    with Image.open(output_path) as image:
        assert image.size == (20, 22)
