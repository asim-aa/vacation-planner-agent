"""
tools/flight_tool.py is v2, backed by a live, quota-limited RapidAPI
subscription (20 requests/month on the free tier). The default test run
must NOT make live calls -- these tests cover only the parts of the
module that are pure logic (no network):
  - resolve_airport() on a known/cached airport code (dict lookup, 0 requests)
  - get_baseline_price() (operates on an already-fetched results list)

Live-call tests (resolve_city_to_airport, search_flights_by_ids against
the real API) are gated behind RUN_LIVE_FLIGHT_TESTS=1 so they never run
by accident and burn scarce quota -- run them deliberately, rarely:
    RUN_LIVE_FLIGHT_TESTS=1 pytest tests/test_flight_tool.py -v
"""

import os

import pytest

from tools.flight_tool import get_baseline_price, resolve_airport, search_flights_by_ids

live_only = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_FLIGHT_TESTS") != "1",
    reason="live RapidAPI call -- set RUN_LIVE_FLIGHT_TESTS=1 to run (costs quota)",
)


def test_resolve_airport_known_code_hits_local_cache_no_network():
    result = resolve_airport("JFK")
    assert result == {"skyId": "JFK", "entityId": "95565058"}


def test_resolve_airport_known_code_is_case_insensitive():
    assert resolve_airport("jfk") == resolve_airport("JFK")


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
def test_live_search_flights_by_ids_returns_real_results():
    jfk = resolve_airport("JFK")
    atl = resolve_airport("ATL")
    results = search_flights_by_ids(jfk, atl, "2026-09-15", limit=5)
    assert results
    prices = [r["Price_USD"] for r in results]
    assert prices == sorted(prices)
