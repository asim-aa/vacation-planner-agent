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

import tools.hotel_tool as hotel_tool_module
from tools.hotel_tool import search_hotels, select_hotel

live_only = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_HOTEL_TESTS") != "1",
    reason="live network call (Google Hotels scrape) -- set RUN_LIVE_HOTEL_TESTS=1 to run",
)

RESULTS_BY_PRICE = [
    {"HotelName": "Budget Inn", "EstimatedPriceUSD": 60.0, "GuestRating": 3.5},
    {"HotelName": "Mid Hotel", "EstimatedPriceUSD": 90.0, "GuestRating": 4.8},
    {"HotelName": "Splurge Suites", "EstimatedPriceUSD": 140.0, "GuestRating": 4.8},
]


def test_select_hotel_cheapest_returns_first_result():
    assert select_hotel(RESULTS_BY_PRICE, optimize_for="cheapest") == RESULTS_BY_PRICE[0]


def test_select_hotel_quality_picks_highest_rating():
    # Mid Hotel and Splurge Suites tie on rating (4.8) -- quality mode
    # should still prefer the cheaper of the two, not just "spend more".
    assert select_hotel(RESULTS_BY_PRICE, optimize_for="quality") == RESULTS_BY_PRICE[1]


def test_select_hotel_quality_ignores_missing_ratings():
    results = [
        {"HotelName": "Unrated", "EstimatedPriceUSD": 200.0, "GuestRating": None},
        {"HotelName": "Rated", "EstimatedPriceUSD": 90.0, "GuestRating": 4.0},
    ]
    assert select_hotel(results, optimize_for="quality")["HotelName"] == "Rated"


class _FakeHotel:
    name = "Test Hotel"
    price = 100.0
    rating = 4.5
    amenities = []
    url = "http://example.com"


class _FakeHotelResult:
    hotels = [_FakeHotel()]


def test_search_hotels_caches_repeated_identical_calls(monkeypatch):
    search_hotels.cache_clear()
    calls = {"n": 0}

    def fake_get_hotels(**kwargs):
        calls["n"] += 1
        return _FakeHotelResult()

    monkeypatch.setattr(hotel_tool_module, "get_hotels", fake_get_hotels)

    search_hotels("Paris", "2027-04-15", "2027-04-21", limit=5)
    search_hotels("Paris", "2027-04-15", "2027-04-21", limit=5)

    assert calls["n"] == 1


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
