# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import functools
import logging

import joblib

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = "./fallback_cache"


def fallback_cache(cache_dir: str = _DEFAULT_CACHE_DIR):
    """Return a decorator that falls back to cached results after wrapped-function failures.

    Each call attempts to execute the function and update the cache on success.
    If the function raises before any matching cache exists, a RuntimeError is raised.
    """
    memory = joblib.Memory(cache_dir, verbose=0)

    def decorator(func):
        cached_func = memory.cache(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call check_call_in_cache upfront to initialize joblib's func_code file,
            # ensuring fallback detection works correctly after an exception.
            has_cache = cached_func.check_call_in_cache(*args, **kwargs)  # type: ignore[attr-defined]
            try:
                output, _ = cached_func.call(*args, **kwargs)  # type: ignore[attr-defined]
                return output
            except Exception as e:
                if has_cache:
                    logger.warning("%s raised %s. Using cached result.", func.__name__, type(e).__name__)
                    return cached_func(*args, **kwargs)
                raise RuntimeError(f"{func.__name__} raised an exception and no cache is available") from e

        return wrapper

    return decorator
