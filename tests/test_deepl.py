# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import joblib

from arxiv_upvote_trends import deepl as deepl_module


@patch("arxiv_upvote_trends.deepl.deepl.DeepLClient")
def test_translate_abstract_to_japanese_uses_deepl_sdk(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPL_AUTH_KEY", "deepl-key")
    mock_client = mock_client_cls.return_value
    mock_client.translate_text.return_value = [SimpleNamespace(text="日本語の要約")]

    result = deepl_module._translate_abstract.__wrapped__("2604.00001", "EN", "JA", "English abstract")

    mock_client_cls.assert_called_once_with("deepl-key")
    mock_client.translate_text.assert_called_once_with(["English abstract"], source_lang="EN", target_lang="JA")
    assert result == [deepl_module.TranslationSentence("English abstract", "日本語の要約")]


@patch("arxiv_upvote_trends.deepl.deepl.DeepLClient")
def test_translate_abstract_to_japanese_pairs_each_sentence(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPL_AUTH_KEY", "deepl-key")
    mock_client = mock_client_cls.return_value
    mock_client.translate_text.return_value = [
        SimpleNamespace(text="最初の文。"),
        SimpleNamespace(text="次の文。"),
    ]

    result = deepl_module._translate_abstract.__wrapped__(
        "2604.00001",
        "EN",
        "JA",
        "First sentence. Next sentence.",
    )

    mock_client.translate_text.assert_called_once_with(
        ["First sentence.", "Next sentence."],
        source_lang="EN",
        target_lang="JA",
    )
    assert result == [
        deepl_module.TranslationSentence("First sentence.", "最初の文。"),
        deepl_module.TranslationSentence("Next sentence.", "次の文。"),
    ]


def test_format_japanese_translation_text_uses_translated_sentences_only():
    result = deepl_module.format_japanese_translation_text(
        [
            deepl_module.TranslationSentence("First sentence.", "最初の文。"),
            deepl_module.TranslationSentence("Next sentence.", "次の文。"),
        ]
    )

    assert result == "最初の文。\n\n次の文。"


@patch("arxiv_upvote_trends.deepl.deepl.DeepLClient")
def test_translate_abstract_to_japanese_skips_when_auth_key_is_missing(mock_client_cls, monkeypatch):
    monkeypatch.delenv("DEEPL_AUTH_KEY", raising=False)

    result = deepl_module.translate_abstract_to_japanese("2604.00001", "English abstract")

    mock_client_cls.assert_not_called()
    assert result is None


@patch("arxiv_upvote_trends.deepl.deepl.DeepLClient")
def test_translate_abstract_to_japanese_cache_ignores_abstract(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPL_AUTH_KEY", "deepl-key")
    mock_client = mock_client_cls.return_value
    mock_client.translate_text.return_value = [SimpleNamespace(text="最初の訳")]
    cached_translate = joblib.Memory(str(tmp_path / "deepl-cache"), verbose=0).cache(
        deepl_module._translate_abstract.__wrapped__,
        ignore=["abstract"],
    )

    first = cached_translate("2604.00001", "EN", "JA", "First abstract")
    second = cached_translate("2604.00001", "EN", "JA", "Updated abstract")

    assert first == [deepl_module.TranslationSentence("First abstract", "最初の訳")]
    assert second == [deepl_module.TranslationSentence("First abstract", "最初の訳")]
    mock_client.translate_text.assert_called_once_with(["First abstract"], source_lang="EN", target_lang="JA")


@patch("arxiv_upvote_trends.deepl.joblib.Memory")
def test_prune_deepl_translation_cache_uses_retention_age(mock_memory_cls, tmp_path):
    deepl_module.prune_deepl_translation_cache(str(tmp_path / "deepl-cache"), retention_days=60)

    mock_memory_cls.assert_called_once_with(str(tmp_path / "deepl-cache"), verbose=0)
    mock_memory_cls.return_value.reduce_size.assert_called_once_with(age_limit=timedelta(days=60))
