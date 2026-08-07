"""
tools/flight_tool.py is v3, backed by fast-flights (scrapes Google
Flights, no API key, no formal quota) plus fully offline airport
resolution via airportsdata. resolve_city_to_iata() is pure local lookup
so it's tested directly; search_flights()/get_baseline_price() make a
real (free, unrestricted) network call, gated the same way the earlier
quota-limited tests were, in case Google ever rate-limits or blocks the
scraper -- keeps the default suite fast and independent of that.
"""

import os

import pytest

from tools.flight_tool import get_baseline_price, resolve_city_to_iata, search_flights

live_only = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_FLIGHT_TESTS") != "1",
    reason="live network call (Google Flights scrape) -- set RUN_LIVE_FLIGHT_TESTS=1 to run",
)


def test_resolve_city_to_iata_known_city():
    assert resolve_city_to_iata("Paris", "France") == "CDG"


def test_resolve_city_to_iata_disambiguates_by_country():
    # "Paris" alone matches multiple airports across countries (including
    # small US towns literally named Paris) -- country narrows correctly.
    assert resolve_city_to_iata("Paris", "France") != resolve_city_to_iata("Paris", "USA")


def test_resolve_city_to_iata_unknown_city_returns_none():
    assert resolve_city_to_iata("Nowhereland") is None


def test_get_baseline_price_averages_given_results():
    results = [
        {"Price_USD": 100.0},
        {"Price_USD": 200.0},
        {"Price_USD": 300.0},
    ]
    assert get_baseline_price(results) == 200.0


def test_get_baseline_price_empty_list_returns_none():
    assert get_baseline_price([]) is None


@live_only
def test_live_search_flights_returns_real_results():
    results = search_flights("JFK", "ATL", "2026-09-15", limit=5)
    assert results
    prices = [r["Price_USD"] for r in results]
    assert prices == sorted(prices)


@live_only
def test_live_search_flights_unknown_route_returns_empty():
    assert search_flights("XXX", "YYY", "2026-09-15") == []
