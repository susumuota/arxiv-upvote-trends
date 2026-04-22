# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, cast

import pandas as pd
from pdf2image import convert_from_path
from PIL import Image


@dataclass(frozen=True)
class ReportRow:
    """One paper row for the top-paper report."""

    rank: int
    arxiv_id: str
    title: str
    authors: str
    score: int
    num_comments: int
    count: int
    alphaxiv_score: int
    huggingface_score: int
    huggingface_comments: int
    arxiv_url: str
    alphaxiv_url: str
    huggingface_url: str
    source_urls: tuple[str, ...]


def build_report_rows(
    df_stats: pd.DataFrame,
    ax_papers: list[dict],
    hf_papers: list[dict],
    limit: int = 30,
) -> list[ReportRow]:
    """Combine aggregated stats with raw alphaXiv and Hugging Face paper metadata."""
    ax_by_id = _index_papers(ax_papers, ("universal_paper_id", "arxiv_id", "id", "paper_id"))
    hf_by_id = _index_papers(hf_papers, ("id", "paper_id", "arxiv_id"))

    rows = []
    for rank, stat in enumerate(df_stats.head(limit).to_dict("records"), start=1):
        arxiv_id = _text(stat.get("arxiv_id"))
        ax_paper = ax_by_id.get(arxiv_id, {})
        hf_paper = hf_by_id.get(arxiv_id, {})
        source_urls = tuple(_iter_urls(stat.get("url")))
        alphaxiv_url = _source_url(source_urls, "alphaxiv.org") or _alphaxiv_url(arxiv_id, ax_paper)
        huggingface_url = _source_url(source_urls, "huggingface.co") or _huggingface_url(arxiv_id, hf_paper)

        rows.append(
            ReportRow(
                rank=rank,
                arxiv_id=arxiv_id,
                title=_title(hf_paper, ax_paper, arxiv_id),
                authors=_authors(hf_paper) or _authors(ax_paper),
                score=_int(stat.get("score")),
                num_comments=_int(stat.get("num_comments")),
                count=_int(stat.get("count")),
                alphaxiv_score=_alphaxiv_score(ax_paper),
                huggingface_score=_int(hf_paper.get("upvotes")),
                huggingface_comments=_int(hf_paper.get("comments")),
                arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
                alphaxiv_url=alphaxiv_url,
                huggingface_url=huggingface_url,
                source_urls=source_urls,
            )
        )
    return rows


def render_report_html(
    rows: list[ReportRow],
    output_path: str | Path,
    generated_at: datetime | None = None,
) -> Path:
    """Render the top-paper report as a static HTML file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    html = report_html(rows, generated_at=generated_at)
    output.write_text(html, encoding="utf-8")
    return output


def report_html(rows: list[ReportRow], generated_at: datetime | None = None) -> str:
    """Return the top-paper report as an HTML string."""
    generated = generated_at or datetime.now(tz=UTC)
    generated_text = generated.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total_score = sum(row.score for row in rows)
    total_comments = sum(row.num_comments for row in rows)
    source_hits = sum(row.count for row in rows)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>arXiv Upvote Trends Top {len(rows)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<main class="page">
  <header class="report-header">
    <div>
      <p class="kicker">alphaXiv + Hugging Face</p>
      <h1>arXiv Upvote Trends Top {len(rows)}</h1>
      <p class="generated">Generated {escape(generated_text)}</p>
    </div>
    <dl class="summary">
      <div><dt>Papers</dt><dd>{len(rows)}</dd></div>
      <div><dt>Score</dt><dd>{total_score:,}</dd></div>
      <div><dt>Comments</dt><dd>{total_comments:,}</dd></div>
      <div><dt>Source Hits</dt><dd>{source_hits:,}</dd></div>
    </dl>
  </header>
  <section class="paper-list" aria-label="Top papers">
    {_paper_rows_html(rows)}
  </section>
</main>
</body>
</html>
"""


def render_report_pdf(html_path: str | Path, output_path: str | Path) -> Path:
    """Render a report HTML file to PDF with WeasyPrint."""
    from weasyprint import HTML

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=Path(html_path)).write_pdf(output)
    return output


def convert_pdf_to_png(pdf_path: str | Path, output_path: str | Path, dpi: int = 180) -> Path:
    """Convert a report PDF to a single PNG image."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(pdf_path, dpi=dpi)
    if not images:
        raise ValueError(f"No pages found in PDF: {pdf_path}")

    if len(images) == 1:
        _trim_bottom_margin(images[0]).save(output, "PNG")
        return output

    width = max(image.width for image in images)
    height = sum(image.height for image in images)
    combined = Image.new("RGB", (width, height), "white")
    offset = 0
    for image in images:
        left = (width - image.width) // 2
        combined.paste(image, (left, offset))
        offset += image.height
    _trim_bottom_margin(combined).save(output, "PNG")
    return output


def _paper_rows_html(rows: list[ReportRow]) -> str:
    return "\n".join(_paper_row_html(row) for row in rows)


def _paper_row_html(row: ReportRow) -> str:
    links = _links_html(row)
    authors = f'<p class="authors">{escape(row.authors)}</p>' if row.authors else ""
    return f"""    <article class="paper">
      <div class="rank">{row.rank}</div>
      <div class="paper-main">
        <h2>{escape(row.title)}</h2>
        {authors}
        <div class="meta">
          <span>{escape(row.arxiv_id)}</span>
          {links}
        </div>
      </div>
      <div class="metrics">
        <div class="metric total"><span>Total</span><strong>{row.score:,}</strong></div>
        <div class="metric"><span>alphaXiv</span><strong>{row.alphaxiv_score:,}</strong></div>
        <div class="metric"><span>HF</span><strong>{row.huggingface_score:,}</strong></div>
        <div class="metric"><span>Comments</span><strong>{row.num_comments:,}</strong></div>
      </div>
    </article>"""


def _links_html(row: ReportRow) -> str:
    links = [
        ("arXiv", row.arxiv_url),
        ("alphaXiv", row.alphaxiv_url),
        ("Hugging Face", row.huggingface_url),
    ]
    return "".join(f'<a href="{escape(url)}">{escape(label)}</a>' for label, url in links if url)


def _index_papers(papers: list[dict], keys: Iterable[str]) -> dict[str, dict]:
    indexed = {}
    for paper in papers:
        arxiv_id = _first_text(paper, keys)
        if arxiv_id and arxiv_id not in indexed:
            indexed[arxiv_id] = paper
    return indexed


def _title(hf_paper: dict, ax_paper: dict, arxiv_id: str) -> str:
    return (
        _first_text(hf_paper, ("title", "paper_title"))
        or _first_text(ax_paper, ("title", "paper_title"))
        or f"arXiv:{arxiv_id}"
    )


def _authors(paper: dict) -> str:
    authors = paper.get("authors")
    if isinstance(authors, str):
        return authors
    if not isinstance(authors, list):
        return ""

    names = []
    for author in authors:
        if isinstance(author, str):
            names.append(author)
        elif isinstance(author, dict):
            name = _first_text(author, ("name", "full_name", "username"))
            if name:
                names.append(name)
    return ", ".join(names[:6])


def _alphaxiv_score(paper: dict) -> int:
    metrics = paper.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    return _int(metrics.get("public_total_votes"))


def _alphaxiv_url(arxiv_id: str, paper: dict) -> str:
    return _first_text(paper, ("url", "html_url")) or (f"https://www.alphaxiv.org/abs/{arxiv_id}" if arxiv_id else "")


def _huggingface_url(arxiv_id: str, paper: dict) -> str:
    return _first_text(paper, ("url", "html_url")) or (f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else "")


def _source_url(urls: Iterable[str], host: str) -> str:
    return next((url for url in urls if host in url), "")


def _iter_urls(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [_text(item) for item in value if _text(item)]
    return []


def _first_text(mapping: dict, keys: Iterable[str]) -> str:
    return next((_text(mapping.get(key)) for key in keys if _text(mapping.get(key))), "")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _trim_bottom_margin(image: Image.Image, margin: int = 72, threshold: int = 8) -> Image.Image:
    rgb_image = image.convert("RGB")
    background = cast(tuple[int, int, int], rgb_image.getpixel((0, rgb_image.height - 1)))
    step = 8

    for y in range(rgb_image.height - 1, -1, -1):
        for x in range(0, rgb_image.width, step):
            pixel = cast(tuple[int, int, int], rgb_image.getpixel((x, y)))
            if any(abs(pixel[i] - background[i]) > threshold for i in range(3)):
                bottom = min(rgb_image.height, y + margin)
                return rgb_image.crop((0, 0, rgb_image.width, bottom))
    return rgb_image


_CSS = """
@page {
  size: 1400px 5000px;
  margin: 0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #eef1f4;
  color: #19212a;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 18px;
  letter-spacing: 0;
}

.page {
  width: 1400px;
  padding: 48px;
  background: #f8fafc;
}

.report-header {
  padding-bottom: 28px;
  border-bottom: 4px solid #1d4f64;
}

.kicker {
  margin: 0 0 10px;
  color: #1d4f64;
  font-size: 19px;
  font-weight: 800;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: #101820;
  font-size: 62px;
  line-height: 1;
}

.generated {
  margin: 14px 0 0;
  color: #5b6773;
  font-size: 18px;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 24px 0 0;
}

.summary div {
  padding: 14px;
  background: #ffffff;
  border: 1px solid #d7dee6;
  border-radius: 8px;
}

.summary dt {
  color: #5b6773;
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
}

.summary dd {
  margin: 5px 0 0;
  color: #101820;
  font-size: 28px;
  font-weight: 850;
}

.paper-list {
  padding-top: 24px;
}

.paper {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr) 410px;
  gap: 18px;
  align-items: center;
  min-height: 61px;
  padding: 10px 14px 10px 10px;
  background: #ffffff;
  border: 1px solid #dbe2e8;
  border-radius: 8px;
}

.paper + .paper {
  margin-top: 10px;
}

.rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: #1d4f64;
  border-radius: 50%;
  color: #ffffff;
  font-size: 20px;
  font-weight: 850;
}

.paper-main {
  min-width: 0;
}

h2 {
  margin: 0;
  overflow: hidden;
  color: #101820;
  font-size: 19px;
  line-height: 1.18;
}

.authors {
  margin: 3px 0 0;
  overflow: hidden;
  color: #5b6773;
  font-size: 14px;
  line-height: 1.25;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 5px;
  color: #65717e;
  font-size: 13px;
  font-weight: 700;
}

.meta span,
.meta a {
  color: #39536a;
  text-decoration: none;
}

.meta a {
  padding-left: 8px;
  border-left: 1px solid #cbd5df;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.metric {
  min-width: 0;
  padding: 8px 7px;
  background: #f3f6f8;
  border-radius: 7px;
  text-align: right;
}

.metric span {
  display: block;
  overflow: hidden;
  color: #687684;
  font-size: 11px;
  font-weight: 850;
  text-transform: uppercase;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.metric strong {
  display: block;
  margin-top: 2px;
  color: #17212b;
  font-size: 22px;
  line-height: 1;
}

.metric.total {
  background: #e5f3ee;
}

.metric.total strong {
  color: #126044;
}
"""
