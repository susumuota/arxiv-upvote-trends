# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pandas as pd
import pytest
from atproto import models
from atproto_client.utils.text_builder import TextBuilder

import main as main_module
from arxiv_upvote_trends.bluesky import LinkCard
from arxiv_upvote_trends.deepl import TranslationSentence
from arxiv_upvote_trends.report import ReportSource

_STUB_LINK_CARD = LinkCard(title="Page Title", description="Page description", thumb=b"fake-image")


@pytest.fixture(autouse=True)
def _skip_bluesky_post_wait(monkeypatch):
    monkeypatch.setattr(main_module, "_BLUESKY_POST_WAIT", 0)


def test_main_requires_bluesky_handle(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    post_to_bluesky = Mock()
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)

    with pytest.raises(ValueError, match="BLUESKY_HANDLE"):
        main_module.main()

    post_to_bluesky.assert_not_called()


def test_main_requires_bluesky_app_password(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    post_to_bluesky = Mock()
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)

    with pytest.raises(ValueError, match="BLUESKY_APP_PASSWORD"):
        main_module.main()

    post_to_bluesky.assert_not_called()


def test_main_posts_top_n_report_to_bluesky_without_new_rows(monkeypatch):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    post_to_bluesky = Mock(return_value=_post_result("example"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    _stub_pipeline(monkeypatch)

    main_module.main()

    post_to_bluesky.assert_called_once()
    report_arg = post_to_bluesky.call_args.args[0]
    assert isinstance(report_arg, TextBuilder)
    assert report_arg.build_text() == f"arXiv Upvote Trends Top {main_module._REPORT_LIMIT}\nNo papers found."
    assert post_to_bluesky.call_args.kwargs == {
        "image_path": Path("reports/top_n.png"),
        "image_alt": "",
        "timeout": 60,
    }


def test_main_converts_pdf_to_png(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "post_to_bluesky", Mock(return_value=_post_result("report")))
    mocks = _stub_pipeline(monkeypatch)

    main_module.main()

    mocks["convert_pdf_to_png"].assert_called_once_with(
        Path("reports/top_n.pdf"),
        "reports/top_n.png",
        100,
        main_module.MAX_IMAGE_BYTES,
    )


def test_main_continues_when_bluesky_post_fails(monkeypatch, caplog):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "GCS_BUCKET", "cache-bucket")
    _set_bluesky_credentials(monkeypatch)
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
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == []
    restore_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    save_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    assert "Skipping Bluesky post for 2604.00001 after RuntimeError." in caplog.text
    assert "Skipping Bluesky Top N report after RuntimeError." in caplog.text


def test_main_saves_persistent_data_when_report_render_fails(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "GCS_BUCKET", "cache-bucket")
    _set_bluesky_credentials(monkeypatch)
    restore_dir = Mock()
    save_dir = Mock()
    monkeypatch.setattr(main_module, "restore_dir", restore_dir)
    monkeypatch.setattr(main_module, "save_dir", save_dir)
    monkeypatch.setattr(main_module, "post_to_bluesky", Mock(return_value=_post_result("example")))
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [_report_row("2604.00001", is_new=True)]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")
    mocks["render_report_html"].side_effect = RuntimeError("render failed")

    with pytest.raises(RuntimeError, match="render failed"):
        main_module.main()

    restore_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == ["2604.00001"]
    save_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")


def test_main_does_not_save_when_persistent_data_restore_fails(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "GCS_BUCKET", "cache-bucket")
    _set_bluesky_credentials(monkeypatch)
    restore_dir = Mock(side_effect=RuntimeError("restore failed"))
    save_dir = Mock()
    monkeypatch.setattr(main_module, "restore_dir", restore_dir)
    monkeypatch.setattr(main_module, "save_dir", save_dir)

    with pytest.raises(RuntimeError, match="restore failed"):
        main_module.main()

    restore_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    save_dir.assert_not_called()


def test_main_logs_pipeline_error_when_save_after_failure_fails(monkeypatch, caplog):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "GCS_BUCKET", "cache-bucket")
    _set_bluesky_credentials(monkeypatch)
    monkeypatch.setattr(main_module, "restore_dir", Mock())
    save_dir = Mock(side_effect=RuntimeError("save failed"))
    monkeypatch.setattr(main_module, "save_dir", save_dir)
    monkeypatch.setattr(main_module, "post_to_bluesky", Mock(return_value=_post_result("example")))
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [_report_row("2604.00001", is_new=True)]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")
    mocks["render_report_html"].side_effect = ValueError("report failed")

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="save failed"):
        main_module.main()

    save_dir.assert_called_once_with("cache-bucket", "persistent_data.tar.gz", "./persistent_data")
    assert "Pipeline failed" in caplog.text
    assert "ValueError: report failed" in caplog.text


def test_main_posts_each_new_first_page_to_bluesky(monkeypatch, caplog):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    post_to_bluesky = Mock(return_value=_post_result("example"))
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

    with caplog.at_level(logging.INFO):
        main_module.main()

    assert mocks["capture_arxiv_first_page"].call_args_list == [
        call("2604.00003", Path("reports/2604.00003.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
        call("2604.00002", Path("reports/2604.00002.png"), max_output_bytes=main_module.MAX_IMAGE_BYTES),
    ]
    assert post_to_bluesky.call_count == 9
    assert post_to_bluesky.call_args_list[0].args[0].build_text() == (
        "[3/3] 10 Upvotes, 0 Comments, 1 Posts, arXiv:2604.00003\n\n🆕Paper 3"
    )
    assert post_to_bluesky.call_args_list[0].kwargs == {
        "image_path": Path("reports/2604.00003.png"),
        "image_alt": "First page of arXiv:2604.00003: Paper 3",
    }
    assert post_to_bluesky.call_args_list[4].args[0].build_text() == (
        "[2/3] 10 Upvotes, 0 Comments, 1 Posts, arXiv:2604.00002\n\n🆕Paper 2"
    )
    assert post_to_bluesky.call_args_list[4].kwargs == {
        "image_path": Path("reports/2604.00002.png"),
        "image_alt": "First page of arXiv:2604.00002: Paper 2",
    }
    report_arg = post_to_bluesky.call_args_list[8].args[0]
    assert isinstance(report_arg, TextBuilder)
    assert report_arg.build_text() == f"arXiv Upvote Trends Top {main_module._REPORT_LIMIT}\n[1/3] [2/3] [3/3]"
    facets = report_arg.build_facets()
    assert len(facets) == 3
    links = [f.features[0] for f in facets]
    assert all(isinstance(link, models.AppBskyRichtextFacet.Link) for link in links)
    assert links[0].uri == "https://arxiv.org/abs/2604.00001"
    assert links[1].uri == "https://arxiv.org/abs/2604.00002"
    assert links[2].uri == "https://arxiv.org/abs/2604.00003"
    assert post_to_bluesky.call_args_list[8].kwargs == {
        "image_path": Path("reports/top_n.png"),
        "image_alt": (
            "1/3 https://arxiv.org/abs/2604.00001\n"
            "2/3 https://arxiv.org/abs/2604.00002\n"
            "3/3 https://arxiv.org/abs/2604.00003"
        ),
        "timeout": 60,
    }
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == ["2604.00003", "2604.00002"]
    assert "Updating ranking history for 2 posted papers: ['2604.00003', '2604.00002']" in caplog.text


def test_main_filters_non_arxiv_ids_before_reporting(monkeypatch):
    _set_base_config(monkeypatch)
    monkeypatch.setattr(main_module, "post_to_bluesky", Mock(return_value=_post_result("example")))
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
    monkeypatch.setattr(main_module, "post_to_bluesky", Mock(return_value=_post_result("example")))
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


def test_main_does_not_update_history_when_first_page_capture_fails(monkeypatch):
    _set_base_config(monkeypatch)
    post_to_bluesky = Mock(return_value=_post_result("report"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True)
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].side_effect = RuntimeError("pdf failed")

    main_module.main()

    assert post_to_bluesky.call_count == 1
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == []


def test_main_posts_reply_thread_ordered_by_score(monkeypatch):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    paper_result = _post_result("paper")
    hf_result = _post_result("hf")
    ax_result = _post_result("ax")
    links_result = _post_result("links")
    report_result = _post_result("report")
    post_to_bluesky = Mock(side_effect=[paper_result, hf_result, ax_result, links_result, report_result])
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True)
    row.sources = _sources("2604.00001", ax_score=8, hf_score=20, hf_comments=3)
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    main_module.main()

    assert post_to_bluesky.call_count == 5
    hf_call = post_to_bluesky.call_args_list[1]
    assert "Hugging Face" in hf_call.args[0].build_text()
    assert "(1/2)" in hf_call.args[0].build_text()
    assert "20 Upvotes" in hf_call.args[0].build_text()
    assert "3 Comments" in hf_call.args[0].build_text()
    _assert_reply_ref(hf_call, root_uri="at://did/paper", parent_uri="at://did/paper")
    ax_call = post_to_bluesky.call_args_list[2]
    assert "alphaXiv" in ax_call.args[0].build_text()
    assert "(2/2)" in ax_call.args[0].build_text()
    assert "8 Upvotes" in ax_call.args[0].build_text()
    _assert_reply_ref(ax_call, root_uri="at://did/paper", parent_uri="at://did/hf")
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == ["2604.00001"]


def test_main_posts_alphaxiv_reply_under_paper_when_hf_reply_fails(monkeypatch):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    paper_result = _post_result("paper")
    ax_result = _post_result("ax")
    links_result = _post_result("links")
    report_result = _post_result("report")
    post_to_bluesky = Mock(
        side_effect=[paper_result, RuntimeError("hf failed"), ax_result, links_result, report_result]
    )
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True)
    row.sources = _sources("2604.00001", ax_score=8, hf_score=20)
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    main_module.main()

    assert post_to_bluesky.call_count == 5
    ax_call = post_to_bluesky.call_args_list[2]
    _assert_reply_ref(ax_call, root_uri="at://did/paper", parent_uri="at://did/paper")
    mocks["update_ranking_history"].assert_called_once()
    assert mocks["update_ranking_history"].call_args.args[1] == ["2604.00001"]


def test_main_posts_japanese_translation_after_source_replies(monkeypatch):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    paper_result = _post_result("paper")
    hf_result = _post_result("hf")
    ax_result = _post_result("ax")
    translation_result = _post_result("translation")
    report_result = _post_result("report")
    links_result = _post_result("links")
    post_to_bluesky = Mock(
        side_effect=[paper_result, hf_result, ax_result, links_result, translation_result, report_result]
    )
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True, abstract="English abstract")
    row.sources = _sources("2604.00001", ax_score=8, hf_score=20, hf_comments=3)
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")
    translation_sentences = [
        TranslationSentence("First sentence.", "最初の文。"),
        TranslationSentence("Next sentence.", "次の文。"),
    ]
    mocks["translate_abstract_to_japanese"].return_value = translation_sentences
    mocks["render_translation_html"].return_value = Path("reports/2604.00001-ja-abstract.html")
    mocks["render_report_pdf"].side_effect = [
        Path("reports/2604.00001-ja-abstract.pdf"),
        Path("reports/top_n.pdf"),
    ]
    mocks["convert_pdf_to_png"].side_effect = [
        Path("reports/2604.00001-ja-abstract.png"),
        Path("reports/top_n.png"),
    ]

    main_module.main()

    assert post_to_bluesky.call_count == 6
    mocks["translate_abstract_to_japanese"].assert_called_once_with("2604.00001", "English abstract")
    mocks["render_translation_html"].assert_called_once_with(
        row,
        translation_sentences,
        Path("reports/2604.00001-ja-abstract.html"),
    )
    translation_call = post_to_bluesky.call_args_list[4]
    assert translation_call.args[0].build_text() == "最初の文。\n\n次の文。"
    assert translation_call.kwargs["image_path"] == Path("reports/2604.00001-ja-abstract.png")
    assert translation_call.kwargs["image_alt"] == "最初の文。\n\n次の文。"
    _assert_reply_ref(translation_call, root_uri="at://did/paper", parent_uri="at://did/links")


def test_main_skips_japanese_translation_when_abstract_is_empty(monkeypatch):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    post_to_bluesky = Mock(return_value=_post_result("example"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True, abstract="")
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")

    main_module.main()

    mocks["translate_abstract_to_japanese"].assert_not_called()


def test_main_continues_when_japanese_translation_fails(monkeypatch, caplog):
    _set_base_config(monkeypatch)
    _set_bluesky_credentials(monkeypatch)
    post_to_bluesky = Mock(return_value=_post_result("example"))
    monkeypatch.setattr(main_module, "post_to_bluesky", post_to_bluesky)
    row = _report_row("2604.00001", is_new=True, abstract="English abstract")
    mocks = _stub_pipeline(monkeypatch)
    mocks["build_report_rows"].return_value = [row]
    mocks["capture_arxiv_first_page"].return_value = Path("reports/2604.00001.png")
    mocks["translate_abstract_to_japanese"].side_effect = RuntimeError("deepl failed")

    with caplog.at_level(logging.WARNING):
        main_module.main()

    assert "Skipping Japanese abstract reply for 2604.00001 after RuntimeError." in caplog.text
    report_arg = post_to_bluesky.call_args_list[-1].args[0]
    assert report_arg.build_text() == f"arXiv Upvote Trends Top {main_module._REPORT_LIMIT}\n[1/1]"


def _set_base_config(monkeypatch):
    monkeypatch.setattr(main_module, "GCS_BUCKET", "")
    monkeypatch.setattr(main_module, "HF_REPO_ID", "")
    _set_bluesky_credentials(monkeypatch)


def _set_bluesky_credentials(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "user.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-password")


def _post_result(label: str) -> Mock:
    return Mock(uri=f"at://did/{label}", cid=f"cid-{label}")


def _assert_reply_ref(post_call, *, root_uri: str, parent_uri: str) -> None:
    reply_ref = post_call.kwargs["reply_to"]
    assert reply_ref.root.uri == root_uri
    assert reply_ref.parent.uri == parent_uri


def _stub_pipeline(monkeypatch, stats: pd.DataFrame | None = None) -> dict[str, Mock]:
    mocks = {
        "build_report_rows": Mock(return_value=[]),
        "capture_arxiv_first_page": Mock(),
        "convert_pdf_to_png": Mock(return_value=Path("reports/top_n.png")),
        "prune_deepl_translation_cache": Mock(),
        "render_report_html": Mock(return_value=Path("reports/top_n.html")),
        "render_report_pdf": Mock(return_value=Path("reports/top_n.pdf")),
        "render_translation_html": Mock(return_value=Path("reports/2604.00001-ja-abstract.html")),
        "translate_abstract_to_japanese": Mock(return_value=None),
        "update_ranking_history": Mock(),
    }
    monkeypatch.setattr(main_module, "search_alphaxiv", Mock(return_value=[]))
    monkeypatch.setattr(main_module, "search_huggingface", Mock(return_value=[]))
    monkeypatch.setattr(main_module, "load_ranking_history", Mock(return_value={}))
    monkeypatch.setattr(main_module, "update_ranking_history", mocks["update_ranking_history"])
    monkeypatch.setattr(
        main_module,
        "aggregate_stats",
        Mock(return_value=stats if stats is not None else _empty_stats()),
    )
    monkeypatch.setattr(main_module, "build_report_rows", mocks["build_report_rows"])
    monkeypatch.setattr(main_module, "capture_arxiv_first_page", mocks["capture_arxiv_first_page"])
    monkeypatch.setattr(main_module, "convert_pdf_to_png", mocks["convert_pdf_to_png"])
    monkeypatch.setattr(main_module, "prune_deepl_translation_cache", mocks["prune_deepl_translation_cache"])
    monkeypatch.setattr(main_module, "render_report_html", mocks["render_report_html"])
    monkeypatch.setattr(main_module, "render_report_pdf", mocks["render_report_pdf"])
    monkeypatch.setattr(main_module, "render_translation_html", mocks["render_translation_html"])
    monkeypatch.setattr(main_module, "translate_abstract_to_japanese", mocks["translate_abstract_to_japanese"])
    monkeypatch.setattr(main_module, "fetch_link_card", Mock(return_value=_STUB_LINK_CARD))
    return mocks


def _empty_stats() -> pd.DataFrame:
    return pd.DataFrame(columns=["arxiv_id", "score", "num_comments", "count", "url"])


def _report_row(arxiv_id: str, is_new: bool, rank: int = 1, abstract: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        rank=rank,
        arxiv_id=arxiv_id,
        title=f"Paper {rank}",
        authors="",
        abstract=abstract,
        score=10,
        num_comments=0,
        count=1,
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        sources=_sources(arxiv_id, ax_score=5, hf_score=5),
        is_new=is_new,
    )


def _sources(arxiv_id: str, *, ax_score: int, hf_score: int, hf_comments: int = 0) -> tuple[ReportSource, ...]:
    return (
        ReportSource(
            "alphaxiv",
            f"https://www.alphaxiv.org/abs/{arxiv_id}",
            ax_score,
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
        ReportSource(
            "huggingface",
            f"https://huggingface.co/papers/{arxiv_id}",
            hf_score,
            num_comments=hf_comments,
            published_at=datetime(2026, 5, 2, tzinfo=UTC),
        ),
    )
