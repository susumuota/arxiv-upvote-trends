# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import pytest

from arxiv_upvote_trends import fallback_cache


@pytest.fixture
def cache_dir(tmp_path):
    return str(tmp_path / "cache")


def make_flaky(cache_dir, fail_ids: set[int]):
    """Return a function that raises on call numbers listed in fail_ids."""
    call_count = {"n": 0}

    @fallback_cache(cache_dir=cache_dir)
    def flaky_fetch(item_id: int) -> str:
        call_count["n"] += 1
        if call_count["n"] in fail_ids:
            raise RuntimeError("simulated failure")
        return f"result_{item_id}_v{call_count['n']}"

    return flaky_fetch


def test_returns_result_on_success(cache_dir):
    fetch = make_flaky(cache_dir, fail_ids=set())
    assert fetch(1) == "result_1_v1"


def test_raises_when_no_cache(cache_dir):
    fetch = make_flaky(cache_dir, fail_ids={1})
    with pytest.raises(RuntimeError, match="no cache is available"):
        fetch(1)


def test_fallback_to_cache_on_failure(cache_dir):
    fetch = make_flaky(cache_dir, fail_ids={2})
    first = fetch(1)  # succeeds -> cache created
    second = fetch(1)  # fails -> falls back to cache
    assert second == first


def test_cache_updated_on_success(cache_dir):
    fetch = make_flaky(cache_dir, fail_ids=set())
    first = fetch(1)  # v1
    second = fetch(1)  # v2, fresh result
    assert second != first
