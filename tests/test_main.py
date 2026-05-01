# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from pathlib import Path
from unittest.mock import Mock

import pandas as pd

import main as main_module


def test_main_skips_bluesky_when_handle_is_empty(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    post_to_bluesky = Mock()
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    _stub_pipeline(monkeypatch)

    main_module.main()

    post_to_bluesky.assert_not_called()


def test_main_posts_to_bluesky_without_passing_config(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    post_to_bluesky = Mock(return_value=Mock(uri="at://did/example", cid="cid-value"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    _stub_pipeline(monkeypatch)

    main_module.main()

    post_to_bluesky.assert_called_once()
    assert post_to_bluesky.call_args.args[0].startswith("arXiv Upvote Trends\nNo papers found.\nGenerated ")
    assert post_to_bluesky.call_args.kwargs == {}


def test_main_filters_non_arxiv_ids_before_reporting(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    stats = pd.DataFrame(
        [
            {"arxiv_id": "2604.00001", "score": 10, "num_comments": 1, "count": 1, "url": ["valid"]},
            {"arxiv_id": "deepseek-v4", "score": 100, "num_comments": 0, "count": 1, "url": ["invalid"]},
        ]
    )
    mocks = _stub_pipeline(monkeypatch, stats=stats)

    main_module.main()

    filtered_stats = mocks["build_report_rows"].call_args.args[0]
    assert filtered_stats["arxiv_id"].to_list() == ["2604.00001"]
    mocks["capture_arxiv_first_page"].assert_called_once_with("2604.00001", "top1.png")


def _set_base_config(monkeypatch):
    monkeypatch.setattr(main_module, "GCS_BUCKET", "")
    monkeypatch.setattr(main_module, "HF_REPO_ID", "")
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)


def _stub_pipeline(monkeypatch, stats: pd.DataFrame | None = None) -> dict[str, Mock]:
    mocks = {
        "build_report_rows": Mock(return_value=[]),
        "capture_arxiv_first_page": Mock(),
        "convert_pdf_to_png": Mock(return_value=Path("reports/top30.png")),
        "render_report_html": Mock(return_value=Path("reports/top30.html")),
        "render_report_pdf": Mock(return_value=Path("reports/top30.pdf")),
    }
    monkeypatch.setattr(main_module, "search_alphaxiv", Mock(return_value=[]))
    monkeypatch.setattr(main_module, "search_huggingface", Mock(return_value=[]))
    monkeypatch.setattr(
        main_module,
        "aggregate_stats",
        Mock(return_value=stats if stats is not None else _empty_stats()),
    )
    monkeypatch.setattr(main_module, "build_report_rows", mocks["build_report_rows"])
    monkeypatch.setattr(main_module, "capture_arxiv_first_page", mocks["capture_arxiv_first_page"])
    monkeypatch.setattr(main_module, "convert_pdf_to_png", mocks["convert_pdf_to_png"])
    monkeypatch.setattr(main_module, "render_report_html", mocks["render_report_html"])
    monkeypatch.setattr(main_module, "render_report_pdf", mocks["render_report_pdf"])
    return mocks


def _empty_stats() -> pd.DataFrame:
    return pd.DataFrame(columns=["arxiv_id", "score", "num_comments", "count", "url"])
