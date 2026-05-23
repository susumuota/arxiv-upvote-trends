# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import re

# Reference: https://info.arxiv.org/help/arxiv_identifier.html
_NEW_ARXIV_ID_RE = re.compile(
    r"(?:"
    r"(?:0[7-9](?:0[4-9]|1[0-2])|1[0-4](?:0[1-9]|1[0-2]))\.(?!0000)\d{4}"
    r"|"
    r"(?:1[5-9]|[2-9]\d|0[0-6])(?:0[1-9]|1[0-2])\.(?!00000)\d{5}"
    r")(?:v[1-9]\d*)?"
)

_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(" + _NEW_ARXIV_ID_RE.pattern + r")")


def is_arxiv_id(arxiv_id: str) -> bool:
    """Return whether a value is a valid arXiv ID."""
    return bool(_NEW_ARXIV_ID_RE.fullmatch(arxiv_id.strip()))


def parse_arxiv_ids(url: str) -> list[str]:
    """Extract arXiv IDs from a URL, stripping version suffixes."""
    if not url:
        return []
    return [_strip_version(m) for m in _ARXIV_URL_RE.findall(url)]


def _strip_version(arxiv_id: str) -> str:
    i = arxiv_id.find("v")
    return arxiv_id[:i] if i != -1 else arxiv_id
