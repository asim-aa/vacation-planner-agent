"""
Simple TTL cache for live, network-backed search functions. Not meant
for production-scale correctness -- it's in-memory, per-process, and
has no eviction beyond expiry -- it exists to avoid the obvious cost of
"replanning or refining the exact same trip re-scrapes everything from
scratch," both for real usage and for demoing.

`time.time()` is used directly since this is a plain, always-running
module (not a Workflow script, where it's unavailable).
"""

import time
from functools import wraps

DEFAULT_TTL_SECONDS = 15 * 60


def ttl_cache(ttl_seconds: float = DEFAULT_TTL_SECONDS):
    """Cache a function's return value per distinct (args, kwargs) for
    `ttl_seconds`. The wrapped function gets a `.cache_clear()` method,
    same convention as `functools.lru_cache`, for tests to reset state.
    """

    def decorator(fn):
        cache: dict = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()

            cached = cache.get(key)
            if cached is not None:
                cached_at, value = cached
                if now - cached_at < ttl_seconds:
                    return value

            value = fn(*args, **kwargs)
            cache[key] = (now, value)
            return value

        wrapper.cache_clear = cache.clear
        return wrapper

    return decorator
