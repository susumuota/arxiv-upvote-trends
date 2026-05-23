# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
from PIL import Image

from arxiv_upvote_trends.deepl import TranslationSentence
from arxiv_upvote_trends.report import (
    ReportRow,
    ReportSource,
    build_report_rows,
    convert_pdf_to_png,
    render_report_html,
    render_translation_html,
    report_html,
)

_DT = datetime(2026, 5, 1, tzinfo=UTC)


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
            "publication_date": "2026-04-20T12:00:00.000Z",
        },
        {
            "universal_paper_id": "2604.00002",
            "title": "alphaXiv only title",
            "metrics": {"public_total_votes": 4},
            "publication_date": "2026-04-21T08:30:00.000Z",
        },
    ]
    hf_papers = [
        {
            "id": "2604.00001",
            "title": "Hugging Face title",
            "authors": [{"name": "Ada"}, {"name": "Grace"}],
            "upvotes": 7,
            "comments": 2,
            "published_at": "2026-04-22 00:00:00+00:00",
        }
    ]

    rows = build_report_rows(df_stats, ax_papers, hf_papers, [], limit=30)

    assert rows == [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="Hugging Face title",
            authors="Ada, Grace",
            score=17,
            num_comments=2,
            count=2,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=(
                ReportSource(
                    "alphaxiv",
                    "https://www.alphaxiv.org/abs/2604.00001",
                    10,
                    published_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                ),
                ReportSource(
                    "huggingface",
                    "https://huggingface.co/papers/2604.00001",
                    7,
                    num_comments=2,
                    published_at=datetime(2026, 4, 22, 0, 0, tzinfo=UTC),
                ),
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
            arxiv_url="https://arxiv.org/abs/2604.00002",
            sources=(
                ReportSource(
                    "alphaxiv",
                    "https://www.alphaxiv.org/abs/2604.00002",
                    4,
                    published_at=datetime(2026, 4, 21, 8, 30, tzinfo=UTC),
                ),
            ),
        ),
    ]


def test_build_report_rows_extracts_abstract_with_hf_priority():
    df_stats = pd.DataFrame(
        [
            {"arxiv_id": "2604.00001", "score": 17, "num_comments": 0, "count": 2, "url": []},
            {"arxiv_id": "2604.00002", "score": 4, "num_comments": 0, "count": 1, "url": []},
            {"arxiv_id": "2604.00003", "score": 1, "num_comments": 0, "count": 1, "url": []},
        ]
    )
    ax_papers = [
        {"universal_paper_id": "2604.00001", "title": "Paper 1", "abstract": "alphaXiv abstract"},
        {"universal_paper_id": "2604.00002", "title": "Paper 2", "abstract": "only alphaXiv"},
    ]
    hf_papers = [
        {"id": "2604.00001", "title": "Paper 1", "summary": "HF summary"},
    ]

    rows = build_report_rows(df_stats, ax_papers, hf_papers, [])

    assert rows[0].abstract == "HF summary"
    assert rows[1].abstract == "only alphaXiv"
    assert rows[2].abstract == ""


def test_build_report_rows_respects_limit():
    df_stats = pd.DataFrame(
        [
            {"arxiv_id": f"2604.{index:05}", "score": index, "num_comments": 0, "count": 1, "url": []}
            for index in range(3)
        ]
    )

    rows = build_report_rows(df_stats, [], [], [], limit=2)

    assert [row.arxiv_id for row in rows] == ["2604.00000", "2604.00001"]


def test_build_report_rows_marks_known_papers_as_not_new():
    df_stats = pd.DataFrame(
        [
            {"arxiv_id": "2604.00001", "score": 10, "num_comments": 0, "count": 1, "url": []},
            {"arxiv_id": "2604.00002", "score": 5, "num_comments": 0, "count": 1, "url": []},
        ]
    )

    rows = build_report_rows(df_stats, [], [], [], known_arxiv_ids={"2604.00001"})

    assert rows[0].is_new is False
    assert rows[1].is_new is True


def test_build_report_rows_defaults_all_new():
    df_stats = pd.DataFrame([{"arxiv_id": "2604.00001", "score": 10, "num_comments": 0, "count": 1, "url": []}])

    rows = build_report_rows(df_stats, [], [], [])

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
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(ax_score=1),
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
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(ax_score=8, hf_score=4),
        ),
        ReportRow(
            rank=2,
            arxiv_id="2604.00002",
            title="Second paper",
            authors="",
            score=5,
            num_comments=1,
            count=1,
            arxiv_url="https://arxiv.org/abs/2604.00002",
            sources=_sources(ax_score=5),
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
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(ax_score=2),
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
            arxiv_url="https://arxiv.org/abs/2604.00002",
            sources=_sources(ax_score=1),
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
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(ax_score=2, ax_url="https://www.alphaxiv.org/abs/2604.00001"),
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
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(ax_score=8, hf_score=4),
        )
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert (
        '<div class="score-total">12<small>Total</small><span class="score-comments">3 comments</span></div>' in html
    )
    assert '<div class="score-comments">3<small>Comments</small></div>' not in html


def test_render_report_html_writes_file(tmp_path):
    output_path = tmp_path / "top_n.html"

    result = render_report_html([], output_path, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert result == output_path
    assert "arXiv Upvote Trends Top 0" in output_path.read_text(encoding="utf-8")


def test_render_translation_html_writes_file(tmp_path):
    output_path = tmp_path / "translation.html"
    row = ReportRow(
        rank=1,
        arxiv_id="2604.00001",
        title="Paper title",
        authors="Alice",
        score=10,
        num_comments=1,
        count=1,
        arxiv_url="https://arxiv.org/abs/2604.00001",
        sources=(),
    )

    result = render_translation_html(
        row,
        [
            TranslationSentence("This is the first sentence.", "これは最初の文です。"),
            TranslationSentence("This is the second sentence.", "これは次の文です。"),
        ],
        output_path,
        generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC),
    )

    html = output_path.read_text(encoding="utf-8")
    assert result == output_path
    assert '<html lang="ja">' in html
    assert "Paper title" in html
    assert "This is the first sentence." in html
    assert "これは最初の文です。" in html
    assert "This is the second sentence." in html
    assert "これは次の文です。" in html
    assert html.index("This is the first sentence.") < html.index("これは最初の文です。")
    assert html.index("これは最初の文です。") < html.index("This is the second sentence.")


def _sources(
    *,
    ax_score: int = 0,
    hf_score: int = 0,
    hn_score: int = 0,
    ax_url: str = "",
    hf_url: str = "",
    hn_url: str = "",
    hf_comments: int = 0,
    hn_comments: int = 0,
) -> tuple[ReportSource, ...]:
    sources = []
    if ax_url or ax_score:
        sources.append(ReportSource("alphaxiv", ax_url, ax_score, published_at=_DT))
    if hf_url or hf_score or hf_comments:
        sources.append(ReportSource("huggingface", hf_url, hf_score, num_comments=hf_comments, published_at=_DT))
    if hn_url or hn_score or hn_comments:
        sources.append(ReportSource("hackernews", hn_url, hn_score, num_comments=hn_comments, published_at=_DT))
    return tuple(sources)


def test_build_report_rows_includes_hackernews_source():
    df_stats = pd.DataFrame(
        [
            {
                "arxiv_id": "2604.00001",
                "score": 120,
                "num_comments": 5,
                "count": 3,
                "url": [
                    "https://www.alphaxiv.org/abs/2604.00001",
                    "https://huggingface.co/papers/2604.00001",
                    "https://news.ycombinator.com/item?id=12345",
                ],
            },
        ]
    )
    ax_papers = [
        {
            "universal_paper_id": "2604.00001",
            "title": "alphaXiv title",
            "metrics": {"public_total_votes": 10},
            "publication_date": "2026-04-20T12:00:00.000Z",
        },
    ]
    hf_papers = [
        {
            "id": "2604.00001",
            "title": "HF title",
            "upvotes": 7,
            "comments": 2,
            "published_at": "2026-04-22 00:00:00+00:00",
        },
    ]
    hn_papers = [
        {
            "objectID": "12345",
            "url": "https://arxiv.org/abs/2604.00001",
            "points": 103,
            "num_comments": 3,
            "created_at_i": 1745280000,
        },
    ]

    rows = build_report_rows(df_stats, ax_papers, hf_papers, hn_papers, limit=30)

    assert len(rows) == 1
    assert len(rows[0].sources) == 3
    hn_source = rows[0].sources[2]
    assert hn_source.kind == "hackernews"
    assert hn_source.url == "https://news.ycombinator.com/item?id=12345"
    assert hn_source.score == 103
    assert hn_source.num_comments == 3
    assert hn_source.label == "Hacker News"


def test_report_html_includes_hackernews_bar():
    rows = [
        ReportRow(
            rank=1,
            arxiv_id="2604.00001",
            title="Paper with HN",
            authors="",
            score=20,
            num_comments=3,
            count=2,
            arxiv_url="https://arxiv.org/abs/2604.00001",
            sources=_sources(
                ax_score=8,
                hn_score=12,
                hn_url="https://news.ycombinator.com/item?id=99",
            ),
        )
    ]

    html = report_html(rows, generated_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC))

    assert '<a class="tag link hn" href="https://news.ycombinator.com/item?id=99">Hacker News</a>' in html
    assert "bar-hn" in html
    assert "cap-hn" in html
    assert "HN 12" in html


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
