"""
tools/hotel_tool.py is v2, backed by fast-hotels (scrapes Google Hotels,
no API key, no formal quota, but real network calls -- typically a few
seconds each and dependent on Google's page structure). Gated behind
RUN_LIVE_HOTEL_TESTS=1 to keep the default suite fast and independent of
that, same principle as the flight tests:
    RUN_LIVE_HOTEL_TESTS=1 pytest tests/test_hotel_tool.py -v

Known limitation (see tools/hotel_tool.py): Google Hotels' search is
fuzzy about location -- a nonsense city string can return results from
some nearby/default area instead of an empty list. Real destination
names (the only kind the orchestrator ever passes in practice) are not
affected.
"""

import os

import pytest

from tools.hotel_tool import search_hotels

live_only = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_HOTEL_TESTS") != "1",
    reason="live network call (Google Hotels scrape) -- set RUN_LIVE_HOTEL_TESTS=1 to run",
)


@live_only
def test_filters_by_city_and_returns_real_data():
    results = search_hotels("Paris", "2026-09-15", "2026-09-18", limit=5)
    assert results
    assert all(r["cityName"] == "Paris" for r in results)
    assert all(r["EstimatedPriceUSD"] > 0 for r in results)


@live_only
def test_filters_by_max_price():
    results = search_hotels("Paris", "2026-09-15", "2026-09-18", max_price=100, limit=10)
    assert results
    assert all(r["EstimatedPriceUSD"] <= 100 for r in results)


@live_only
def test_results_sorted_cheapest_first():
    results = search_hotels("Paris", "2026-09-15", "2026-09-18", limit=10)
    prices = [r["EstimatedPriceUSD"] for r in results]
    assert prices == sorted(prices)
