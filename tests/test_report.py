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


def test_build_report_rows_marks_known_papers_as_not_new():
    df_stats = pd.DataFrame(
        [
            {"arxiv_id": "2604.00001", "score": 10, "num_comments": 0, "count": 1, "url": []},
            {"arxiv_id": "2604.00002", "score": 5, "num_comments": 0, "count": 1, "url": []},
        ]
    )

    rows = build_report_rows(df_stats, [], [], known_arxiv_ids={"2604.00001"})

    assert rows[0].is_new is False
    assert rows[1].is_new is True


def test_build_report_rows_defaults_all_new():
    df_stats = pd.DataFrame([{"arxiv_id": "2604.00001", "score": 10, "num_comments": 0, "count": 1, "url": []}])

    rows = build_report_rows(df_stats, [], [])

    assert rows[0].is_new is True


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


def test_report_html_summarizes_totals_in_generated_line():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="First paper",
            authors="",
            score=12,
            num_comments=3,
            count=2,
            alphaxiv_score=8,
            huggingface_score=4,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
        ),
        ReportRow(
            rank=2,
            arxiv_id="2604.00002",
            title="Second paper",
            authors="",
            score=5,
            num_comments=1,
            count=1,
            alphaxiv_score=5,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00002",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
        ),
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert "Generated 2026-04-23 00:00 UTC · 2 papers · total upvotes 17 · comments 4" in html
    assert '<dl class="summary">' not in html
    assert "Total Score" not in html
    assert '<p class="footer">' not in html
    assert "Source hits" not in html


def test_report_html_marks_new_papers():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="New paper",
            authors="",
            score=2,
            num_comments=0,
            count=1,
            alphaxiv_score=2,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
            is_new=True,
        ),
        ReportRow(
            rank=2,
            arxiv_id="2604.00002",
            title="Known paper",
            authors="",
            score=1,
            num_comments=0,
            count=1,
            alphaxiv_score=1,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00002",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
            is_new=False,
        ),
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert '<article class="paper top1 new-paper">' in html
    assert '<span class="tag new">NEW</span>' in html
    assert '<article class="paper top2 new-paper">' not in html
    assert html.count('<span class="tag new">NEW</span>') == 1
    assert html.index(">arXiv:2604.00001</a>") < html.index('<span class="tag new">NEW</span>')


def test_report_html_links_arxiv_id_to_abs_page():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="Linked paper",
            authors="",
            score=2,
            num_comments=0,
            count=1,
            alphaxiv_score=2,
            huggingface_score=0,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="https://www.alphaxiv.org/abs/2604.00001",
            huggingface_url="",
            source_urls=(),
        )
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert '<a class="tag link arxiv" href="https://arxiv.org/abs/2604.00001">arXiv:2604.00001</a>' in html
    assert '<span class="tag">2604.00001</span>' not in html
    assert '<a class="tag link arxiv" href="https://arxiv.org/abs/2604.00001">arXiv</a>' not in html
    assert '<a class="tag link ax" href="https://www.alphaxiv.org/abs/2604.00001">alphaXiv</a>' in html


def test_report_html_places_comments_under_total_score():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="Commented paper",
            authors="",
            score=12,
            num_comments=3,
            count=1,
            alphaxiv_score=8,
            huggingface_score=4,
            huggingface_comments=0,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            alphaxiv_url="",
            huggingface_url="",
            source_urls=(),
        )
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert (
        '<div class="score-total">12<small>Total</small><span class="score-comments">3 comments</span></div>' in html
    )
    assert '<div class="score-comments">3<small>Comments</small></div>' not in html


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


def test_convert_pdf_to_png_retries_with_lower_dpi_when_too_large(tmp_path):
    output_path = tmp_path / "report.png"
    large_images = [Image.new("RGB", (40, 40), "white")]
    small_images = [Image.new("RGB", (10, 10), "white")]

    with patch(
        "arxiv_upvote_trends.report.convert_from_path",
        side_effect=[large_images, small_images],
    ) as mock_convert:
        result = convert_pdf_to_png("report.pdf", output_path, max_output_bytes=90, min_dpi=140)

    assert result == output_path
    assert [call.kwargs["dpi"] for call in mock_convert.call_args_list] == [160, 140]
    assert output_path.stat().st_size <= 90
