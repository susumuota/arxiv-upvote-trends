# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

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


def test_main_continues_when_bluesky_post_fails(monkeypatch, caplog):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "GCS_BUCKET", "cache-bucket")
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    post_to_bluesky = Mock(side_effect=RuntimeError("failed"))
    restore_dir = Mock()
    save_dir = Mock()
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    monkeypatch.setattr(main_module, "restore_dir", restore_dir)
    monkeypatch.setattr(main_module, "save_dir", save_dir)
    _stub_pipeline(monkeypatch)

    with caplog.at_level(logging.WARNING):
        main_module.main()

    post_to_bluesky.assert_called_once()
    restore_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    save_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    assert "Skipping Bluesky post after RuntimeError." in caplog.text


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
    mocks["build_report_rows"].return_value = [_report_row("2604.00001", is_new=True)]

    main_module.main()

    filtered_stats = mocks["build_report_rows"].call_args.args[0]
    assert filtered_stats["arxiv_id"].to_list() == ["2604.00001"]
    mocks["capture_arxiv_first_page"].assert_called_once_with("2604.00001", "reports/2604.00001.png")


def test_main_captures_first_pages_only_for_new_report_rows(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    stats = pd.DataFrame(
        [
            {"arxiv_id": "2604.00001", "score": 10, "num_comments": 1, "count": 1, "url": []},
            {"arxiv_id": "2604.00002", "score": 9, "num_comments": 0, "count": 1, "url": []},
            {"arxiv_id": "2604.00003", "score": 8, "num_comments": 0, "count": 1, "url": []},
        ]
    )
    report_rows = [
        _report_row("2604.00001", is_new=False),
        _report_row("2604.00002", is_new=True),
        _report_row("2604.00003", is_new=True),
    ]
    mocks = _stub_pipeline(monkeypatch, stats=stats)
    mocks["build_report_rows"].return_value = report_rows

    main_module.main()

    assert mocks["capture_arxiv_first_page"].call_args_list == [
        call("2604.00002", "reports/2604.00002.png"),
        call("2604.00003", "reports/2604.00003.png"),
    ]


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
    monkeypatch.setattr(main_module, "load_ranking_history", Mock(return_value={}))
    monkeypatch.setattr(main_module, "update_ranking_history", Mock())
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


def _report_row(arxiv_id: str, is_new: bool) -> SimpleNamespace:
    return SimpleNamespace(arxiv_id=arxiv_id, is_new=is_new)
