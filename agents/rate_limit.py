"""
Request caps for the public deployment.

The planner is exposed as a public Streamlit app with no authentication, and
every "plan" or "refine" action fans out into LLM calls plus live scrapes of
Google Flights, Google Hotels, Overpass, and Open-Meteo. Without a cap, a
single scripted client can drive unbounded LLM spend and get the upstream
sources to rate-limit or block the deployment's IP -- an availability problem
as much as a cost one.

Two independent layers, because they defend against different things:

- **Per-session quotas** bound what one visitor can do. Enforced against
  Streamlit's `session_state`, which is per browser session.
- **A process-wide quota** bounds total throughput across *all* visitors, so a
  distributed burst (or many sessions from one script) still can't run the bill
  up. Enforced against a module-level singleton, which in Streamlit's execution
  model survives script reruns for the life of the server process.

This module deliberately has no Streamlit import. The limiter is a plain object
with an injectable clock, so the policy is unit-testable without spinning up a
UI, and reusable if the graph is ever fronted by FastAPI instead.

Caps are read from the environment (see `.env.example`) so a deployment can
tighten them without a code change. Setting `RATE_LIMIT_ENABLED=false` disables
enforcement entirely, which is the right default for local development.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# Per-session defaults. A genuine user plans a trip a handful of times and
# refines it more often than that; these are set well above real use and well
# below what makes abuse worthwhile.
DEFAULT_SESSION_PLANS = 8
DEFAULT_SESSION_REFINEMENTS = 30

# Process-wide default: 120 planning runs per hour across every visitor.
DEFAULT_GLOBAL_PLANS = 120
DEFAULT_GLOBAL_WINDOW_SECONDS = 3600.0


class RateLimitError(RuntimeError):
    """Raised when an action is refused because a quota is exhausted.

    `retry_after` is the seconds until the action would be permitted again, or
    ``None`` when the quota has no window and therefore never replenishes (a
    per-session cap, which resets only when the visitor starts a new session).
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Quota:
    """`max_calls` permitted per `window_seconds`.

    A `window_seconds` of ``None`` means the quota never replenishes: the
    allowance is for the lifetime of whatever holds the limiter.
    """

    max_calls: int
    window_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")
        if self.window_seconds is not None and self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive when set")


class SlidingWindowLimiter:
    """Sliding-window counter over a deque of timestamps.

    Chosen over a fixed window because a fixed window permits a double-rate
    burst across the boundary (all N at 59:59, all N again at 60:01), and over a
    token bucket because the deque lets us report an exact `retry_after` rather
    than an approximation -- which is what the UI needs to show the user.

    Thread-safe: Streamlit serves sessions from a thread pool, so the
    process-wide limiter is genuinely shared mutable state.
    """

    def __init__(
        self,
        quota: Quota,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._quota = quota
        self._time_fn = time_fn
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    @property
    def quota(self) -> Quota:
        return self._quota

    def _evict(self, now: float) -> None:
        """Drop timestamps that have aged out of the window. Caller holds lock."""
        window = self._quota.window_seconds
        if window is None:
            return
        cutoff = now - window
        while self._events and self._events[0] <= cutoff:
            self._events.popleft()

    def remaining(self) -> int:
        """Calls still permitted right now."""
        with self._lock:
            now = self._time_fn()
            self._evict(now)
            return max(0, self._quota.max_calls - len(self._events))

    def retry_after(self) -> float | None:
        """Seconds until one call frees up, or ``None`` if it never will.

        Returns ``0.0`` when a call is available immediately.
        """
        with self._lock:
            now = self._time_fn()
            self._evict(now)
            if len(self._events) < self._quota.max_calls:
                return 0.0
            window = self._quota.window_seconds
            if window is None:
                return None
            if not self._events:
                # max_calls == 0: the quota is closed and no recorded call can
                # ever age out to reopen it.
                return None
            # The oldest event is the next to expire.
            return max(0.0, (self._events[0] + window) - now)

    def try_acquire(self) -> bool:
        """Consume one call if available. Returns whether it was granted."""
        with self._lock:
            now = self._time_fn()
            self._evict(now)
            if len(self._events) >= self._quota.max_calls:
                return False
            self._events.append(now)
            return True

    def release_latest(self) -> bool:
        """Give back the most recently granted call.

        Used to unwind a multi-limiter acquire that another limiter then
        refused, so a rejected request leaves usage counts untouched.
        """
        with self._lock:
            if not self._events:
                return False
            self._events.pop()
            return True

    def reset(self) -> None:
        """Clear recorded usage. For tests and administrative reset."""
        with self._lock:
            self._events.clear()


class QuotaSet:
    """Named limiters enforced together.

    `acquire` is all-or-nothing: if any limiter refuses, no limiter is charged.
    Without that, a request rejected by the global cap would still burn the
    visitor's session allowance -- penalising them for someone else's traffic.
    """

    def __init__(self, limiters: dict[str, SlidingWindowLimiter]) -> None:
        self._limiters = dict(limiters)

    def __contains__(self, name: str) -> bool:
        return name in self._limiters

    def limiter(self, name: str) -> SlidingWindowLimiter:
        return self._limiters[name]

    def remaining(self, name: str) -> int:
        return self._limiters[name].remaining()

    def acquire(self, names: Iterable[str], action: str = "request") -> None:
        """Consume one call from each named limiter, or raise `RateLimitError`.

        Rolls back every limiter it already charged before raising, so a
        refusal leaves usage counts exactly as they were.
        """
        names = list(names)
        charged: list[str] = []

        for name in names:
            limiter = self._limiters.get(name)
            if limiter is None:
                continue
            if limiter.try_acquire():
                charged.append(name)
                continue

            # Refused -- refund whatever we already took.
            for done in charged:
                self.refund(done)

            wait = limiter.retry_after()
            raise RateLimitError(_refusal_message(action, name, wait), retry_after=wait)

    def refund(self, name: str) -> None:
        """Return one previously granted call to the named limiter."""
        limiter = self._limiters.get(name)
        if limiter is not None:
            limiter.release_latest()

    def reset(self) -> None:
        for limiter in self._limiters.values():
            limiter.reset()


def _refusal_message(action: str, scope: str, wait: float | None) -> str:
    if scope.startswith("global"):
        if wait is None:
            return f"This demo has reached its overall {action} limit."
        return (
            f"This demo is at its shared {action} limit right now. "
            f"Try again in about {_humanise(wait)}."
        )
    return (
        f"You've reached this session's {action} limit. "
        "Reload the page to start a new session."
    )


def _humanise(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(seconds) + 1} seconds"
    minutes = int(seconds // 60) + 1
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = seconds / 3600
    return f"{hours:.1f} hours"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def rate_limiting_enabled() -> bool:
    """Enforcement is on unless explicitly disabled."""
    raw = os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def build_session_quotas(
    time_fn: Callable[[], float] = time.monotonic,
) -> QuotaSet:
    """Per-visitor quotas. One of these is created per Streamlit session."""
    return QuotaSet(
        {
            "session_plans": SlidingWindowLimiter(
                Quota(_env_int("RATE_LIMIT_SESSION_PLANS", DEFAULT_SESSION_PLANS)),
                time_fn=time_fn,
            ),
            "session_refinements": SlidingWindowLimiter(
                Quota(
                    _env_int(
                        "RATE_LIMIT_SESSION_REFINEMENTS", DEFAULT_SESSION_REFINEMENTS
                    )
                ),
                time_fn=time_fn,
            ),
        }
    )


def build_global_quotas(
    time_fn: Callable[[], float] = time.monotonic,
) -> QuotaSet:
    """Process-wide quotas shared by every visitor."""
    return QuotaSet(
        {
            "global_plans": SlidingWindowLimiter(
                Quota(
                    _env_int("RATE_LIMIT_GLOBAL_PLANS", DEFAULT_GLOBAL_PLANS),
                    window_seconds=_env_float(
                        "RATE_LIMIT_GLOBAL_WINDOW_SECONDS",
                        DEFAULT_GLOBAL_WINDOW_SECONDS,
                    ),
                ),
                time_fn=time_fn,
            ),
        }
    )


_GLOBAL_QUOTAS: QuotaSet | None = None
_GLOBAL_LOCK = threading.Lock()


def global_quotas() -> QuotaSet:
    """The process-wide quota singleton, created on first use.

    Streamlit re-executes the script top-to-bottom on every interaction, so
    module-level state is the only thing that persists across reruns and is
    shared between sessions.
    """
    global _GLOBAL_QUOTAS
    if _GLOBAL_QUOTAS is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_QUOTAS is None:
                _GLOBAL_QUOTAS = build_global_quotas()
    return _GLOBAL_QUOTAS


def reset_global_quotas() -> None:
    """Drop the singleton so the next call rebuilds it from the environment."""
    global _GLOBAL_QUOTAS
    with _GLOBAL_LOCK:
        _GLOBAL_QUOTAS = None
