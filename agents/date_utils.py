"""Shared date helpers for agent nodes that need a concrete date derived
from the trip's travel_month (the mock v1 tools didn't need real dates;
the live v2/v3 tools do)."""

from calendar import monthrange
from datetime import date, timedelta

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def next_occurrence_of_month(month_name: str, day: int = 15) -> str:
    """Return YYYY-MM-DD for the next future occurrence of `month_name`
    (e.g. "April"), clamping `day` to that month's length."""
    today = date.today()
    month_num = MONTH_NAMES.index(month_name.strip().lower()) + 1
    year = today.year if month_num >= today.month else today.year + 1
    day = min(day, monthrange(year, month_num)[1])
    return date(year, month_num, day).isoformat()


def add_days(iso_date: str, days: int) -> str:
    """Return `iso_date` (YYYY-MM-DD) plus `days`, as YYYY-MM-DD."""
    y, m, d = (int(part) for part in iso_date.split("-"))
    return (date(y, m, d) + timedelta(days=days)).isoformat()
