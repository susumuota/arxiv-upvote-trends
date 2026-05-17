# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pandas as pd
from atproto import models
from atproto_client.utils.text_builder import TextBuilder

import main as main_module
from arxiv_upvote_trends.bluesky import LinkCard

_STUB_LINK_CARD = LinkCard(title="Page Title", description="Page description", thumb=b"fake-image")


def test_main_skips_bluesky_when_handle_is_empty(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    post_to_bluesky = Mock()
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    _stub_pipeline(monkeypatch)

    main_module.main()

    post_to_bluesky.assert_not_called()


def test_main_posts_top30_report_to_bluesky_without_new_rows(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    post_to_bluesky = Mock(return_value=Mock(uri="at://did/example", cid="cid-value"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    _stub_pipeline(monkeypatch)

    main_module.main()

    post_to_bluesky.assert_called_once()
    report_arg = post_to_bluesky.call_args.args[0]
    assert isinstance(report_arg, TextBuilder)
    assert report_arg.build_text() == "arXiv Upvote Trends Top 30\nNo papers found."
    assert post_to_bluesky.call_args.kwargs == {
        "image_path": Path("reports/top30.png"),
        "image_alt": "",
        "timeout": 60,
    }


def test_main_converts_pdf_to_png(monkeypatch):
    _set_base_config(monkeypatch)
    mocks = _stub_pipeline(monkeypatch)

    main_module.main()

    mocks["convert_pdf_to_png"].assert_called_once_with(
        Path("reports/top30.pdf"),
        "reports/top30.png",
        100,
        main_module.MAX_IMAGE_BYTES,
    )


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
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [_report_row("2604.00001", is_new=True)]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    with caplog.at_level(logging.WARNING):
        main_module.main()

    assert post_to_bluesky.call_count == 2
    restore_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    save_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    assert "Skipping Bluesky post for 2604.00001 after RuntimeError." in caplog.text
    assert "Skipping Bluesky top 30 report after RuntimeError." in caplog.text


def test_main_posts_each_new_first_page_to_bluesky(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    post_to_bluesky = Mock(return_value=Mock(uri="at://did/example", cid="cid-value"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    report_rows = [
        _report_row("2604.00001", is_new=False, rank=1),
        _report_row("2604.00002", is_new=True, rank=2),
        _report_row("2604.00003", is_new=True, rank=3),
    ]
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = report_rows
    mocks["capture_arxiv_first_page"].side_effect = [
        Path("reports/2604.00003.png"),
        Path("reports/2604.00002.png"),
    ]

    main_module.main()

    assert mocks["capture_arxiv_first_page"].call_args_list == [
        call("2604.00003", Path("reports/2604.00003.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
        call("2604.00002", Path("reports/2604.00002.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
    ]
    assert post_to_bluesky.call_count == 7
    assert post_to_bluesky.call_args_list[0].args[0].build_text() == (
        "[3/3] 10 Upvotes, 0 Comments, 1 Posts, arXiv:2604.00003\n\n🆕Paper 3"
    )
    assert post_to_bluesky.call_args_list[0].kwargs == {
        "image_path": Path("reports/2604.00003.png"),
        "image_alt": "First page of arXiv:2604.00003: Paper 3",
    }
    assert post_to_bluesky.call_args_list[3].args[0].build_text() == (
        "[2/3] 10 Upvotes, 0 Comments, 1 Posts, arXiv:2604.00002\n\n🆕Paper 2"
    )
    assert post_to_bluesky.call_args_list[3].kwargs == {
        "image_path": Path("reports/2604.00002.png"),
        "image_alt": "First page of arXiv:2604.00002: Paper 2",
    }
    report_arg = post_to_bluesky.call_args_list[6].args[0]
    assert isinstance(report_arg, TextBuilder)
    assert report_arg.build_text() == "arXiv Upvote Trends Top 30\n[1/3] [2/3] [3/3]"
    facets = report_arg.build_facets()
    assert len(facets) == 3
    links = [f.features[0] for f in facets]
    assert all(isinstance(link, models.AppBskyRichtextFacet.Link) for link in links)
    assert links[0].uri == "https://arxiv.org/abs/2604.00001"
    assert links[1].uri == "https://arxiv.org/abs/2604.00002"
    assert links[2].uri == "https://arxiv.org/abs/2604.00003"
    assert post_to_bluesky.call_args_list[6].kwargs == {
        "image_path": Path("reports/top30.png"),
        "image_alt": (
            "1/3 https://arxiv.org/abs/2604.00001\n"
            "2/3 https://arxiv.org/abs/2604.00002\n"
            "3/3 https://arxiv.org/abs/2604.00003"
        ),
        "timeout": 60,
    }


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
    mocks["capture_arxiv_first_page"].assert_called_once_with(
        "2604.00001",
        Path("reports/2604.00001.png"),
        max_output_bytes=main_module.MAX_IMAGE_BYTES,
    )


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
        call("2604.00003", Path("reports/2604.00003.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
        call("2604.00002", Path("reports/2604.00002.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
    ]


def test_main_posts_reply_thread_ordered_by_score(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    paper_result = Mock(uri="at://did/paper", cid="cid-paper")
    hf_result = Mock(uri="at://did/hf", cid="cid-hf")
    ax_result = Mock(uri="at://did/ax", cid="cid-ax")
    report_result = Mock(uri="at://did/report", cid="cid-report")
    post_to_bluesky = Mock(side_effect=[paper_result, hf_result, ax_result, report_result])
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True)
    row.huggingface_score = 20
    row.alphaxiv_score = 8
    row.huggingface_comments = 3
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    main_module.main()

    assert post_to_bluesky.call_count == 4
    hf_call = post_to_bluesky.call_args_list[1]
    assert "Hugging Face" in hf_call.args[0].build_text()
    assert "(1/2)" in hf_call.args[0].build_text()
    assert "20 Upvotes" in hf_call.args[0].build_text()
    assert "3 Comments" in hf_call.args[0].build_text()
    hf_ref = hf_call.kwargs["reply_to"]
    assert hf_ref.root.uri == "at://did/paper"
    assert hf_ref.parent.uri == "at://did/paper"
    ax_call = post_to_bluesky.call_args_list[2]
    assert "alphaXiv" in ax_call.args[0].build_text()
    assert "(2/2)" in ax_call.args[0].build_text()
    assert "8 Upvotes" in ax_call.args[0].build_text()
    ax_ref = ax_call.kwargs["reply_to"]
    assert ax_ref.root.uri == "at://did/paper"
    assert ax_ref.parent.uri == "at://did/hf"


def test_main_posts_alphaxiv_reply_under_paper_when_hf_reply_fails(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    paper_result = Mock(uri="at://did/paper", cid="cid-paper")
    ax_result = Mock(uri="at://did/ax", cid="cid-ax")
    report_result = Mock(uri="at://did/report", cid="cid-report")
    post_to_bluesky = Mock(side_effect=[paper_result, RuntimeError("hf failed"), ax_result, report_result])
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True)
    row.huggingface_score = 20
    row.alphaxiv_score = 8
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    main_module.main()

    assert post_to_bluesky.call_count == 4
    ax_call = post_to_bluesky.call_args_list[2]
    ax_ref = ax_call.kwargs["reply_to"]
    assert ax_ref.root.uri == "at://did/paper"
    assert ax_ref.parent.uri == "at://did/paper"


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
    monkeypatch.setattr(main_module, "fetch_link_card", Mock(return_value=_STUB_LINK_CARD))
    return mocks


def _empty_stats() -> pd.DataFrame:
    return pd.DataFrame(columns=["arxiv_id", "score", "num_comments", "count", "url"])


def _report_row(arxiv_id: str, is_new: bool, rank: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        rank=rank,
        arxiv_id=arxiv_id,
        title=f"Paper {rank}",
        authors="",
        abstract="",
        score=10,
        num_comments=0,
        count=1,
        alphaxiv_score=5,
        huggingface_score=5,
        huggingface_comments=0,
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        alphaxiv_url=f"https://www.alphaxiv.org/abs/{arxiv_id}",
        alphaxiv_published_at=datetime(2026, 5, 1, tzinfo=UTC),
        huggingface_url=f"https://huggingface.co/papers/{arxiv_id}",
        huggingface_published_at=datetime(2026, 5, 2, tzinfo=UTC),
        is_new=is_new,
    )
