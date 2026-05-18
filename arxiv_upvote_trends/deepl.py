# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from typing import cast

import deepl
import joblib

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = "./persistent_data/deepl_translate"
_DEFAULT_RETENTION_DAYS = 60

_memory = joblib.Memory(_DEFAULT_CACHE_DIR, verbose=0)
_segment = cast(Callable[[str, str], list[str]], vars(import_module("sentencex"))["segment"])


@dataclass(frozen=True)
class TranslationSentence:
    """One source sentence and its translated text."""

    source_text: str
    translated_text: str


def translate_abstract_to_japanese(
    arxiv_id: str,
    abstract: str,
    source_lang: str = "EN",
    target_lang: str = "JA",
) -> list[TranslationSentence] | None:
    """Translate an abstract with DeepL, caching by arxiv_id and language."""
    if not abstract.strip():
        return None
    if not os.environ.get("DEEPL_AUTH_KEY", ""):
        logger.info("DEEPL_AUTH_KEY is not set. Skipping abstract translation for %s", arxiv_id)
        return None

    return _translate_abstract(arxiv_id, source_lang, target_lang, abstract)


def format_japanese_translation_text(translation_sentences: list[TranslationSentence]) -> str:
    """Return translated sentences separated by blank lines."""
    return "\n\n".join(sentence.translated_text for sentence in translation_sentences)


def prune_deepl_translation_cache(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
) -> None:
    """Remove DeepL translation cache entries older than retention_days."""
    memory = joblib.Memory(cache_dir, verbose=0)
    memory.reduce_size(age_limit=timedelta(days=retention_days))


@_memory.cache(ignore=["abstract"])
def _translate_abstract(
    arxiv_id: str,
    source_lang: str,
    target_lang: str,
    abstract: str,
) -> list[TranslationSentence]:
    auth_key = os.environ["DEEPL_AUTH_KEY"]
    sentences = _segment_abstract(abstract)
    if not sentences:
        return []
    logger.info("Translating abstract for %s with DeepL", arxiv_id)
    client = deepl.DeepLClient(auth_key)
    result = client.translate_text(sentences, source_lang=source_lang, target_lang=target_lang)
    text_results = cast(list[deepl.TextResult], result if isinstance(result, list) else [result])
    if len(text_results) != len(sentences):
        msg = f"DeepL returned {len(text_results)} translations for {len(sentences)} sentences"
        raise RuntimeError(msg)
    return [
        TranslationSentence(source_text=source_text, translated_text=text_result.text)
        for source_text, text_result in zip(sentences, text_results, strict=True)
    ]


def _segment_abstract(abstract: str) -> list[str]:
    return [sentence.strip() for sentence in _segment("en", abstract) if sentence.strip()]
