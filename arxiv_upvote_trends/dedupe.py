# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Hashable, Iterable


def deduplicate[T](items: Iterable[T], key: Callable[[T], Hashable | None]) -> list[T]:
    """Deduplicate items by key, keeping the first item for each key."""
    seen: set[Hashable] = set()
    return [item for item in items if _mark_new_key(key(item), seen)]


def _mark_new_key(key: Hashable | None, seen: set[Hashable]) -> bool:
    if key is None or key in seen:
        return False
    seen.add(key)
    return True
