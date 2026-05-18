# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
import os
from datetime import timedelta
from typing import cast

import deepl
import joblib

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = "./persistent_data/deepl_translate"
_DEFAULT_RETENTION_DAYS = 60

_memory = joblib.Memory(_DEFAULT_CACHE_DIR, verbose=0)


def translate_abstract_to_japanese(
    arxiv_id: str,
    abstract: str,
    source_lang: str = "EN",
    target_lang: str = "JA",
) -> str | None:
    """Translate an abstract with DeepL, caching by arxiv_id and language."""
    if not abstract.strip():
        return None
    if not os.environ.get("DEEPL_AUTH_KEY", ""):
        logger.info("DEEPL_AUTH_KEY is not set. Skipping abstract translation for %s", arxiv_id)
        return None

    return _translate_abstract(arxiv_id, source_lang, target_lang, abstract)


def prune_deepl_translation_cache(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
) -> None:
    """Remove DeepL translation cache entries older than retention_days."""
    memory = joblib.Memory(cache_dir, verbose=0)
    memory.reduce_size(age_limit=timedelta(days=retention_days))


@_memory.cache(ignore=["abstract"])
def _translate_abstract(arxiv_id: str, source_lang: str, target_lang: str, abstract: str) -> str:
    auth_key = os.environ["DEEPL_AUTH_KEY"]
    logger.info("Translating abstract for %s with DeepL", arxiv_id)
    client = deepl.DeepLClient(auth_key)
    result = client.translate_text(abstract, source_lang=source_lang, target_lang=target_lang)
    if isinstance(result, list):
        text_results = cast(list[deepl.TextResult], result)
        return "\n".join(item.text for item in text_results)
    return cast(deepl.TextResult, result).text
