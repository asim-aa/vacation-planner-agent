"""tools/cache.py is pure/offline -- time.time() is monkeypatched to
control expiry without actually sleeping in tests."""

import tools.cache as cache_module
from tools.cache import ttl_cache


def test_second_call_with_same_args_is_cached_not_recomputed():
    calls = []

    @ttl_cache(ttl_seconds=60)
    def fn(x):
        calls.append(x)
        return x * 2

    assert fn(3) == 6
    assert fn(3) == 6
    assert calls == [3]


def test_different_args_are_not_conflated():
    calls = []

    @ttl_cache(ttl_seconds=60)
    def fn(x):
        calls.append(x)
        return x * 2

    assert fn(3) == 6
    assert fn(4) == 8
    assert calls == [3, 4]


def test_kwargs_are_part_of_the_cache_key():
    calls = []

    @ttl_cache(ttl_seconds=60)
    def fn(x, seat_class=None):
        calls.append((x, seat_class))
        return f"{x}-{seat_class}"

    fn(1, seat_class="Economy")
    fn(1, seat_class="Business")
    assert calls == [(1, "Economy"), (1, "Business")]


def test_expires_after_ttl(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(cache_module.time, "time", lambda: fake_time[0])

    calls = []

    @ttl_cache(ttl_seconds=10)
    def fn(x):
        calls.append(x)
        return x * 2

    fn(3)
    fake_time[0] += 5  # within TTL
    fn(3)
    assert calls == [3]

    fake_time[0] += 10  # now past TTL
    fn(3)
    assert calls == [3, 3]


def test_cache_clear_forces_recompute():
    calls = []

    @ttl_cache(ttl_seconds=60)
    def fn(x):
        calls.append(x)
        return x * 2

    fn(3)
    fn.cache_clear()
    fn(3)
    assert calls == [3, 3]
