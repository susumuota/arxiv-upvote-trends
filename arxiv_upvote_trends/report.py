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

    total_alphaxiv = sum(row.alphaxiv_score for row in rows)
    total_huggingface = sum(row.huggingface_score for row in rows)

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
    <p class="kicker">Live &middot; alphaXiv &times; Hugging Face</p>
    <h1>arXiv Upvote Trends — Top {len(rows)}</h1>
    <p class="generated">Generated {escape(generated_text)}</p>
    <dl class="summary">
      <div><dt>Papers</dt><dd>{len(rows)}</dd></div>
      <div><dt>Total Score</dt><dd>{total_score:,}</dd></div>
      <div><dt>alphaXiv</dt><dd>{total_alphaxiv:,}</dd></div>
      <div><dt>Hugging Face</dt><dd>{total_huggingface:,}</dd></div>
    </dl>
  </header>
  <section class="paper-list" aria-label="Top papers">
    {_paper_rows_html(rows)}
  </section>
  <p class="footer">Total comments {total_comments:,} · Source hits {source_hits:,} · arxiv-upvote-trends</p>
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
    """Convert a report PDF to a single PNG image.

    Multiple pages are stacked vertically before trimming the bottom margin.
    """
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
    max_score = max((row.score for row in rows), default=1) or 1
    return "\n".join(_paper_row_html(row, max_score) for row in rows)


def _paper_row_html(row: ReportRow, max_score: int) -> str:
    authors = f'<p class="authors">{escape(row.authors)}</p>' if row.authors else ""
    ax_pct = row.alphaxiv_score / max_score * 100
    hf_pct = row.huggingface_score / max_score * 100
    rank_class = f" top{row.rank}" if row.rank <= 3 else ""
    return f"""    <article class="paper{rank_class}">
      <div class="rank-badge">
        <span class="rank-num">{row.rank:02d}</span>
        <span class="rank-label">Rank</span>
      </div>
      <div class="paper-main">
        <h2>{escape(row.title)}</h2>
        {authors}
        <div class="meta">
          <span class="tag">{escape(row.arxiv_id)}</span>
          {_link_tags_html(row)}
        </div>
      </div>
      <div class="score-row">
        <div class="score-total">{row.score:,}<small>Total</small></div>
        <div class="bar-col">
          <div class="bar">
            <div class="bar-ax" style="width:{ax_pct:.1f}%"></div>
            <div class="bar-hf" style="width:{hf_pct:.1f}%"></div>
          </div>
          <div class="bar-caption">
            <span class="cap-ax">alphaXiv {row.alphaxiv_score:,}</span>
            <span class="cap-sep">·</span>
            <span class="cap-hf">HF {row.huggingface_score:,}</span>
          </div>
        </div>
        <div class="score-comments">{row.num_comments:,}<small>Comments</small></div>
      </div>
    </article>"""


def _link_tags_html(row: ReportRow) -> str:
    links = [
        ("arXiv", row.arxiv_url, "arxiv"),
        ("alphaXiv", row.alphaxiv_url, "ax"),
        ("Hugging Face", row.huggingface_url, "hf"),
    ]
    return "".join(
        f'<a class="tag link {cls}" href="{escape(url)}">{escape(label)}</a>' for label, url, cls in links if url
    )


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
  size: 1400px 9000px;
  margin: 0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #f4f5f7;
  color: #0f172a;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 17px;
  line-height: 1.3;
}

.page {
  width: 1400px;
  padding: 48px;
}

.report-header {
  padding: 36px 40px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
  border-radius: 24px;
  color: #f8fafc;
}

.kicker {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 16px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.10);
  border-radius: 999px;
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.kicker::before {
  content: "";
  width: 6px;
  height: 6px;
  background: #34d399;
  border-radius: 50%;
}

h1 {
  margin: 0;
  color: #f8fafc;
  font-size: 56px;
  line-height: 1.0;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.generated {
  margin: 14px 0 0;
  color: #94a3b8;
  font-size: 14px;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 24px 0 0;
}

.summary div {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
}

.summary dt {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.summary dd {
  margin: 6px 0 0;
  color: #f8fafc;
  font-size: 28px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 16px;
}

.paper {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 360px;
  gap: 20px;
  align-items: center;
  min-height: 76px;
  padding: 8px 20px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.04);
}

.rank-badge {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}

.rank-num {
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.rank-label {
  color: #94a3b8;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.paper.top1 .rank-num { color: #d97706; }
.paper.top2 .rank-num { color: #64748b; }
.paper.top3 .rank-num { color: #b45309; }

.paper-main {
  min-width: 0;
}

h2 {
  margin: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.25;
  font-weight: 700;
  letter-spacing: -0.005em;
}

.authors {
  margin: 5px 0 0;
  overflow: hidden;
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
  font-size: 11px;
}

.tag {
  padding: 3px 9px;
  background: #eef2f7;
  border-radius: 999px;
  color: #475569;
  font-weight: 600;
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
  text-decoration: none;
}

.tag.link.arxiv { background: #eff6ff; color: #1d4ed8; }
.tag.link.ax { background: #f5f3ff; color: #6d28d9; }
.tag.link.hf { background: #fff7e6; color: #92400e; }

.score-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: center;
}

.bar-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bar-caption {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  align-items: baseline;
  white-space: nowrap;
  color: #64748b;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.bar-caption .cap-sep { color: #cbd5e1; }

.bar-caption .cap-ax::before,
.bar-caption .cap-hf::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 5px;
  border-radius: 2px;
  vertical-align: middle;
}

.bar-caption .cap-ax::before { background: #8b5cf6; }
.bar-caption .cap-hf::before { background: #f59e0b; }

.score-total {
  color: #0f172a;
  font-size: 26px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.score-total small {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.bar {
  display: flex;
  height: 10px;
  overflow: hidden;
  background: #eef2f7;
  border-radius: 999px;
}

.bar-ax {
  height: 100%;
  background: #8b5cf6;
}

.bar-hf {
  height: 100%;
  background: #f59e0b;
}

.score-comments {
  color: #0f172a;
  font-size: 14px;
  line-height: 1;
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.score-comments small {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.footer {
  margin-top: 24px;
  color: #94a3b8;
  font-size: 12px;
  text-align: center;
}
"""
