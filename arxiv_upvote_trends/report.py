# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from collections.abc import Iterable, Set
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd
from pdf2image import convert_from_path
from PIL import Image

from .deepl import TranslationSentence

type ReportSourceKind = Literal["alphaxiv", "huggingface"]

_SOURCE_CLASSES: dict[ReportSourceKind, str] = {
    "alphaxiv": "ax",
    "huggingface": "hf",
}
_SOURCE_LABELS: dict[ReportSourceKind, str] = {
    "alphaxiv": "alphaXiv",
    "huggingface": "Hugging Face",
}
_SOURCE_CAPTIONS: dict[ReportSourceKind, str] = {
    "alphaxiv": "alphaXiv",
    "huggingface": "HF",
}


@dataclass(frozen=True)
class ReportSource:
    """One discussion source for a report row."""

    kind: ReportSourceKind
    url: str
    score: int
    num_comments: int = 0
    published_at: datetime | None = None

    @property
    def label(self) -> str:
        return _SOURCE_LABELS[self.kind]


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
    arxiv_url: str
    sources: tuple[ReportSource, ...]
    abstract: str = ""
    is_new: bool = True


def build_report_rows(
    df_stats: pd.DataFrame,
    ax_papers: list[dict],
    hf_papers: list[dict],
    limit: int = 30,
    known_arxiv_ids: Set[str] = frozenset(),
) -> list[ReportRow]:
    """Combine aggregated stats with raw alphaXiv and Hugging Face paper metadata."""
    ax_by_id = _index_papers(ax_papers, ("universal_paper_id", "arxiv_id", "id", "paper_id"))
    hf_by_id = _index_papers(hf_papers, ("id", "paper_id", "arxiv_id"))

    rows = []
    for rank, stat in enumerate(df_stats.head(limit).to_dict("records"), start=1):
        arxiv_id = _text(stat.get("arxiv_id"))
        ax_paper = ax_by_id.get(arxiv_id, {})
        hf_paper = hf_by_id.get(arxiv_id, {})
        stat_urls = tuple(_iter_urls(stat.get("url")))
        sources = _build_sources(arxiv_id, stat_urls, ax_paper, hf_paper)

        abstract = _first_text(hf_paper, ("summary",)) or _first_text(ax_paper, ("abstract",))

        rows.append(
            ReportRow(
                rank=rank,
                arxiv_id=arxiv_id,
                title=_title(hf_paper, ax_paper, arxiv_id),
                authors=_authors(hf_paper) or _authors(ax_paper),
                score=_int(stat.get("score")),
                num_comments=_int(stat.get("num_comments")),
                count=_int(stat.get("count")),
                arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
                sources=sources,
                abstract=abstract,
                is_new=arxiv_id not in known_arxiv_ids,
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


def render_translation_html(
    row: ReportRow,
    translation_sentences: list[TranslationSentence],
    output_path: str | Path,
    generated_at: datetime | None = None,
) -> Path:
    """Render a Japanese abstract translation as a static HTML file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    html = translation_html(row, translation_sentences, generated_at=generated_at)
    output.write_text(html, encoding="utf-8")
    return output


_TRANSLATION_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Libre+Baskerville:wght@400;700&"
    "family=Noto+Sans+JP:wght@400;500;700;800&"
    "family=Roboto:wght@400;700;800&"
    "display=swap"
)


def translation_html(
    row: ReportRow,
    translation_sentences: list[TranslationSentence],
    generated_at: datetime | None = None,
) -> str:
    """Return a Japanese abstract translation as an HTML string."""
    generated = generated_at or datetime.now(tz=UTC)
    generated_text = generated.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    authors = f'<p class="translation-authors">{escape(row.authors)}</p>' if row.authors else ""
    abstract_html = _translation_sentences_html(translation_sentences)

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<link href="{_TRANSLATION_FONTS_URL}" rel="stylesheet">
<title>Japanese abstract translation for arXiv:{escape(row.arxiv_id)}</title>
<style>
{_TRANSLATION_CSS}
</style>
</head>
<body>
<main class="translation-page">
  <header class="translation-header">
    <p class="translation-kicker">arXiv abstract translation</p>
    <h1>{escape(row.title or row.arxiv_id)}</h1>
    {authors}
    <p class="translation-meta">arXiv:{escape(row.arxiv_id)} · Generated {escape(generated_text)}</p>
  </header>
  <section class="translation-body" aria-label="Japanese abstract translation">
{abstract_html}
  </section>
</main>
</body>
</html>
"""


def _translation_sentences_html(translation_sentences: list[TranslationSentence]) -> str:
    return "\n".join(
        "    "
        f'<p class="translation-sentence">'
        f'<span class="translation-source">{escape(sentence.source_text)}</span>'
        "<br>"
        f'<span class="translation-target">{escape(sentence.translated_text)}</span>'
        "</p>"
        for sentence in translation_sentences
    )


def report_html(rows: list[ReportRow], generated_at: datetime | None = None) -> str:
    """Return the top-paper report as an HTML string."""
    generated = generated_at or datetime.now(tz=UTC)
    generated_text = generated.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total_score = sum(row.score for row in rows)
    total_comments = sum(row.num_comments for row in rows)
    generated_summary = (
        f"{generated_text} · {len(rows):,} papers · total upvotes {total_score:,} · comments {total_comments:,}"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
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
    <p class="generated">Generated {escape(generated_summary)}</p>
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


def convert_pdf_to_png(
    pdf_path: str | Path,
    output_path: str | Path,
    dpi: int = 160,
    max_output_bytes: int | None = None,
    min_dpi: int = 80,
    dpi_step: int = 20,
) -> Path:
    """Convert a report PDF to a single PNG image.

    Multiple pages are stacked vertically before trimming the bottom margin.
    """
    if min_dpi > dpi:
        raise ValueError("min_dpi must be less than or equal to dpi")
    if dpi_step <= 0:
        raise ValueError("dpi_step must be positive")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    current_dpi = dpi
    last_size = 0
    while True:
        images = convert_from_path(pdf_path, dpi=current_dpi)
        if not images:
            raise ValueError(f"No pages found in PDF: {pdf_path}")

        _save_combined_png(images, output)
        last_size = output.stat().st_size
        if max_output_bytes is None or last_size <= max_output_bytes:
            return output
        if current_dpi <= min_dpi:
            break
        current_dpi = max(min_dpi, current_dpi - dpi_step)

    raise ValueError(f"Report image for {pdf_path} is {last_size} bytes at min_dpi={min_dpi}")


def _save_combined_png(images: list[Image.Image], output: Path) -> None:
    if len(images) == 1:
        _trim_bottom_margin(images[0]).save(output, "PNG")
        return

    width = max(image.width for image in images)
    height = sum(image.height for image in images)
    combined = Image.new("RGB", (width, height), "white")
    offset = 0
    for image in images:
        left = (width - image.width) // 2
        combined.paste(image, (left, offset))
        offset += image.height
    _trim_bottom_margin(combined).save(output, "PNG")


def _paper_rows_html(rows: list[ReportRow]) -> str:
    max_score = max((row.score for row in rows), default=1) or 1
    return "\n".join(_paper_row_html(row, max_score) for row in rows)


def _paper_row_html(row: ReportRow, max_score: int) -> str:
    authors = f'<p class="authors">{escape(row.authors)}</p>' if row.authors else ""
    rank_class = f" top{row.rank}" if row.rank <= 3 else ""
    new_class = " new-paper" if row.is_new else ""
    new_tag = '<span class="tag new">NEW</span>' if row.is_new else ""
    comment_label = "comment" if row.num_comments == 1 else "comments"
    comment_tag = f'<span class="score-comments">{row.num_comments:,} {comment_label}</span>'
    return f"""    <article class="paper{rank_class}{new_class}">
      <div class="rank-badge">
        <span class="rank-num">{row.rank:02d}</span>
        <span class="rank-label">Rank</span>
      </div>
      <div class="paper-main">
        <h2>{escape(row.title)}</h2>
        {authors}
        <div class="meta">
          {_arxiv_tag_html(row)}
          {_link_tags_html(row)}
          {new_tag}
        </div>
      </div>
      <div class="score-row">
        <div class="score-total">{row.score:,}<small>Total</small>{comment_tag}</div>
        <div class="bar-col">
          <div class="bar">
            {_source_bar_html(row.sources, max_score)}
          </div>
          <div class="bar-caption">
            {_source_caption_html(row.sources)}
          </div>
        </div>
      </div>
    </article>"""


def _arxiv_tag_html(row: ReportRow) -> str:
    return f'<a class="tag link arxiv" href="{escape(row.arxiv_url)}">arXiv:{escape(row.arxiv_id)}</a>'


def _link_tags_html(row: ReportRow) -> str:
    return "".join(
        f'<a class="tag link {_source_class(source)}" href="{escape(source.url)}">{escape(source.label)}</a>'
        for source in row.sources
        if source.url
    )


def _source_bar_html(sources: tuple[ReportSource, ...], max_score: int) -> str:
    return "\n            ".join(
        f'<div class="bar-{_source_class(source)}" style="width:{source.score / max_score * 100:.1f}%"></div>'
        for source in sources
    )


def _source_caption_html(sources: tuple[ReportSource, ...]) -> str:
    return '\n            <span class="cap-sep">·</span>\n            '.join(
        f'<span class="cap-{_source_class(source)}">{_source_caption(source)} {source.score:,}</span>'
        for source in sources
    )


def _source_class(source: ReportSource) -> str:
    return _SOURCE_CLASSES[source.kind]


def _source_caption(source: ReportSource) -> str:
    return _SOURCE_CAPTIONS[source.kind]


def _build_sources(
    arxiv_id: str,
    stat_urls: tuple[str, ...],
    ax_paper: dict,
    hf_paper: dict,
) -> tuple[ReportSource, ...]:
    sources: list[ReportSource] = []

    alphaxiv_url = _source_url(stat_urls, "alphaxiv.org")
    if alphaxiv_url or ax_paper:
        sources.append(
            ReportSource(
                "alphaxiv",
                alphaxiv_url or _alphaxiv_url(arxiv_id, ax_paper),
                _alphaxiv_score(ax_paper),
                published_at=_published_at(ax_paper, ("publication_date",)),
            )
        )

    huggingface_url = _source_url(stat_urls, "huggingface.co")
    if huggingface_url or hf_paper:
        sources.append(
            ReportSource(
                "huggingface",
                huggingface_url or _huggingface_url(arxiv_id, hf_paper),
                _int(hf_paper.get("upvotes")),
                num_comments=_int(hf_paper.get("comments")),
                published_at=_published_at(hf_paper, ("published_at",)),
            )
        )

    return tuple(sources)


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


def _published_at(paper: dict, keys: Iterable[str]) -> datetime | None:
    for key in keys:
        value = paper.get(key)
        if value:
            return datetime.fromisoformat(str(value))
    return None


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
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-bottom-color: rgba(15, 23, 42, 0.12);
  border-radius: 14px;
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

.paper.new-paper {
  padding-left: 15px;
  background: #ffffff;
  border-left: 5px solid #14b8a6;
}

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
.tag.new { background: #0f766e; color: #ffffff; }

.score-row {
  display: grid;
  grid-template-columns: 72px 1fr;
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
  text-align: right;
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
  display: block;
  margin-top: 5px;
  color: #64748b;
  font-size: 10px;
  line-height: 1.1;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-transform: uppercase;
}

"""


_TRANSLATION_CSS = """
@page {
  size: 1200px 1800px;
  margin: 0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #f7f7f4;
  color: #111827;
  font-family: "Noto Sans JP", sans-serif;
  line-height: 1.65;
}

.translation-page {
  width: 50em;
  min-height: 75em;
  padding: 2em 2.5em;
  font-size: 24px;
}

.translation-header {
  padding-bottom: 1.17em;
  border-bottom: 0.17em solid #0f766e;
}

.translation-kicker {
  margin: 0 0 0.75em;
  color: #0f766e;
  font-size: 0.83em;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: #111827;
  font-family: Roboto, "Noto Sans JP", sans-serif;
  font-size: 1.75em;
  line-height: 1.22;
  font-weight: 800;
  letter-spacing: 0;
}

.translation-authors {
  margin: 0.75em 0 0;
  color: #4b5563;
  font-size: 0.92em;
}

.translation-meta {
  margin: 0.67em 0 0;
  color: #6b7280;
  font-size: 0.75em;
  font-variant-numeric: tabular-nums;
}

.translation-body {
  padding-top: 1.5em;
}

.translation-sentence {
  margin: 0 0 1em;
  color: #111827;
  font-size: 1em;
  line-height: 1.5em;
  font-weight: 400;
  letter-spacing: 0;
}

.translation-source {
  color: #115e59;
  font-family: "Libre Baskerville", "Times New Roman", Times, serif;
  font-size: 1em;
  font-weight: 700;
}

.translation-target {
  color: #111827;
}

"""
