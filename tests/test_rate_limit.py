"""
Tests for the public-deployment request caps.

The clock is injected everywhere, so window behaviour is asserted
deterministically rather than by sleeping.
"""

import threading

import pytest

from agents import rate_limit
from agents.rate_limit import (
    Quota,
    QuotaSet,
    RateLimitError,
    SlidingWindowLimiter,
    build_global_quotas,
    build_session_quotas,
    global_quotas,
    rate_limiting_enabled,
    reset_global_quotas,
)


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Each test starts from documented defaults, not the developer's .env."""
    for key in (
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_SESSION_PLANS",
        "RATE_LIMIT_SESSION_REFINEMENTS",
        "RATE_LIMIT_GLOBAL_PLANS",
        "RATE_LIMIT_GLOBAL_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_global_quotas()
    yield
    reset_global_quotas()


# --------------------------------------------------------------------------
# Quota validation
# --------------------------------------------------------------------------


def test_quota_rejects_negative_max_calls():
    with pytest.raises(ValueError):
        Quota(max_calls=-1)


def test_quota_rejects_non_positive_window():
    with pytest.raises(ValueError):
        Quota(max_calls=5, window_seconds=0)


# --------------------------------------------------------------------------
# SlidingWindowLimiter
# --------------------------------------------------------------------------


def test_allows_exactly_max_calls_then_refuses():
    limiter = SlidingWindowLimiter(Quota(3), time_fn=FakeClock())
    assert [limiter.try_acquire() for _ in range(3)] == [True, True, True]
    assert limiter.try_acquire() is False


def test_remaining_counts_down_and_floors_at_zero():
    limiter = SlidingWindowLimiter(Quota(2), time_fn=FakeClock())
    assert limiter.remaining() == 2
    limiter.try_acquire()
    assert limiter.remaining() == 1
    limiter.try_acquire()
    assert limiter.remaining() == 0
    limiter.try_acquire()  # refused
    assert limiter.remaining() == 0


def test_zero_quota_refuses_everything():
    limiter = SlidingWindowLimiter(Quota(0), time_fn=FakeClock())
    assert limiter.try_acquire() is False
    assert limiter.remaining() == 0


def test_windowless_quota_never_replenishes():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(Quota(1, window_seconds=None), time_fn=clock)
    assert limiter.try_acquire() is True
    clock.advance(10_000_000)
    assert limiter.try_acquire() is False
    assert limiter.retry_after() is None


def test_window_replenishes_after_expiry():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(Quota(2, window_seconds=60), time_fn=clock)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    clock.advance(59)
    assert limiter.try_acquire() is False, "must not replenish before the window closes"

    clock.advance(2)  # now 61s past the first call
    assert limiter.try_acquire() is True


def test_window_slides_rather_than_resetting_wholesale():
    """A fixed window would allow 2N calls across the boundary. A sliding one
    releases capacity one call at a time, as each individual call ages out."""
    clock = FakeClock()
    limiter = SlidingWindowLimiter(Quota(2, window_seconds=60), time_fn=clock)

    limiter.try_acquire()  # t=0
    clock.advance(30)
    limiter.try_acquire()  # t=30
    assert limiter.try_acquire() is False

    clock.advance(31)  # t=61: only the t=0 call has expired
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False, "the t=30 call is still inside the window"


def test_retry_after_reports_time_until_oldest_call_expires():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(Quota(1, window_seconds=100), time_fn=clock)
    limiter.try_acquire()
    clock.advance(40)
    assert limiter.retry_after() == pytest.approx(60)


def test_retry_after_is_zero_when_capacity_available():
    limiter = SlidingWindowLimiter(Quota(2, window_seconds=100), time_fn=FakeClock())
    limiter.try_acquire()
    assert limiter.retry_after() == 0.0


def test_reset_clears_usage():
    limiter = SlidingWindowLimiter(Quota(1), time_fn=FakeClock())
    limiter.try_acquire()
    assert limiter.try_acquire() is False
    limiter.reset()
    assert limiter.try_acquire() is True


def test_limiter_is_thread_safe():
    """20 threads racing a quota of 5 must yield exactly 5 grants."""
    limiter = SlidingWindowLimiter(Quota(5), time_fn=FakeClock())
    grants = []
    lock = threading.Lock()
    barrier = threading.Barrier(20)

    def worker():
        barrier.wait()
        got = limiter.try_acquire()
        with lock:
            grants.append(got)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(grants) == 5


# --------------------------------------------------------------------------
# QuotaSet
# --------------------------------------------------------------------------


def _quota_set(clock, **specs) -> QuotaSet:
    return QuotaSet(
        {
            name: SlidingWindowLimiter(quota, time_fn=clock)
            for name, quota in specs.items()
        }
    )


def test_quota_set_charges_every_named_limiter():
    clock = FakeClock()
    qs = _quota_set(clock, a=Quota(3), b=Quota(3))
    qs.acquire(["a", "b"])
    assert qs.remaining("a") == 2
    assert qs.remaining("b") == 2


def test_quota_set_raises_when_any_limiter_is_exhausted():
    clock = FakeClock()
    qs = _quota_set(clock, plenty=Quota(10), scarce=Quota(1))
    qs.acquire(["plenty", "scarce"])
    with pytest.raises(RateLimitError):
        qs.acquire(["plenty", "scarce"])


def test_quota_set_refunds_when_a_later_limiter_refuses():
    """The headline invariant: a refused request must not silently burn the
    allowance of the limiters that were already charged."""
    clock = FakeClock()
    qs = _quota_set(clock, plenty=Quota(10), scarce=Quota(1))

    qs.acquire(["plenty", "scarce"])
    assert qs.remaining("plenty") == 9

    with pytest.raises(RateLimitError):
        qs.acquire(["plenty", "scarce"])

    assert qs.remaining("plenty") == 9, "the refused attempt must be refunded"


def test_quota_set_ignores_unknown_scope_names():
    clock = FakeClock()
    qs = _quota_set(clock, a=Quota(1))
    qs.acquire(["a", "does_not_exist"])
    assert qs.remaining("a") == 0


def test_quota_set_acquire_with_no_scopes_is_a_noop():
    qs = _quota_set(FakeClock(), a=Quota(1))
    qs.acquire([])
    assert qs.remaining("a") == 1


def test_rate_limit_error_carries_retry_after_for_windowed_quota():
    clock = FakeClock()
    qs = _quota_set(clock, global_plans=Quota(1, window_seconds=600))
    qs.acquire(["global_plans"])
    clock.advance(100)

    with pytest.raises(RateLimitError) as excinfo:
        qs.acquire(["global_plans"])

    assert excinfo.value.retry_after == pytest.approx(500)


def test_rate_limit_error_has_no_retry_after_for_session_quota():
    qs = _quota_set(FakeClock(), session_plans=Quota(1))
    qs.acquire(["session_plans"])
    with pytest.raises(RateLimitError) as excinfo:
        qs.acquire(["session_plans"])
    assert excinfo.value.retry_after is None


def test_session_refusal_message_tells_the_user_to_reload():
    qs = _quota_set(FakeClock(), session_plans=Quota(0))
    with pytest.raises(RateLimitError, match="Reload the page"):
        qs.acquire(["session_plans"], action="trip plan")


def test_global_refusal_message_mentions_waiting_not_reloading():
    clock = FakeClock()
    qs = _quota_set(clock, global_plans=Quota(1, window_seconds=3600))
    qs.acquire(["global_plans"], action="trip plan")

    with pytest.raises(RateLimitError) as excinfo:
        qs.acquire(["global_plans"], action="trip plan")

    message = str(excinfo.value)
    assert "Reload the page" not in message
    assert "Try again in" in message


def test_fully_closed_windowed_quota_reports_no_retry_time():
    """max_calls=0 leaves nothing to age out, so there is no time at which the
    caller could usefully retry -- and asking for one must not crash."""
    limiter = SlidingWindowLimiter(Quota(0, window_seconds=3600), time_fn=FakeClock())
    assert limiter.retry_after() is None

    qs = _quota_set(FakeClock(), global_plans=Quota(0, window_seconds=3600))
    with pytest.raises(RateLimitError) as excinfo:
        qs.acquire(["global_plans"], action="trip plan")
    assert excinfo.value.retry_after is None
    assert "reached its overall" in str(excinfo.value)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_session_quotas_use_documented_defaults():
    qs = build_session_quotas(time_fn=FakeClock())
    assert qs.remaining("session_plans") == rate_limit.DEFAULT_SESSION_PLANS
    assert qs.remaining("session_refinements") == rate_limit.DEFAULT_SESSION_REFINEMENTS


def test_env_overrides_session_caps(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SESSION_PLANS", "2")
    qs = build_session_quotas(time_fn=FakeClock())
    assert qs.remaining("session_plans") == 2


def test_env_overrides_global_window(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PLANS", "1")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_WINDOW_SECONDS", "30")
    clock = FakeClock()
    qs = build_global_quotas(time_fn=clock)

    qs.acquire(["global_plans"])
    with pytest.raises(RateLimitError):
        qs.acquire(["global_plans"])

    clock.advance(31)
    qs.acquire(["global_plans"])


@pytest.mark.parametrize("bad", ["", "   ", "abc", "-5"])
def test_malformed_env_falls_back_to_default(monkeypatch, bad):
    """A typo in deployment config must not silently disable the cap."""
    monkeypatch.setenv("RATE_LIMIT_SESSION_PLANS", bad)
    qs = build_session_quotas(time_fn=FakeClock())
    assert qs.remaining("session_plans") == rate_limit.DEFAULT_SESSION_PLANS


def test_zero_is_a_valid_env_value_meaning_fully_closed(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SESSION_PLANS", "0")
    qs = build_session_quotas(time_fn=FakeClock())
    assert qs.remaining("session_plans") == 0


def test_rate_limiting_is_enabled_by_default():
    assert rate_limiting_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "off", " OFF "])
def test_rate_limiting_can_be_disabled(monkeypatch, value):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", value)
    assert rate_limiting_enabled() is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "anything-else"])
def test_only_explicit_falsey_values_disable(monkeypatch, value):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", value)
    assert rate_limiting_enabled() is True


# --------------------------------------------------------------------------
# Global singleton
# --------------------------------------------------------------------------


def test_global_quotas_are_shared_across_calls():
    """The process-wide cap only works if every session sees the same object."""
    assert global_quotas() is global_quotas()


def test_global_usage_persists_across_lookups(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PLANS", "1")
    reset_global_quotas()

    global_quotas().acquire(["global_plans"])
    with pytest.raises(RateLimitError):
        global_quotas().acquire(["global_plans"])


def test_reset_global_quotas_rebuilds_from_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PLANS", "1")
    reset_global_quotas()
    global_quotas().acquire(["global_plans"])

    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PLANS", "5")
    reset_global_quotas()
    for _ in range(5):
        global_quotas().acquire(["global_plans"])
