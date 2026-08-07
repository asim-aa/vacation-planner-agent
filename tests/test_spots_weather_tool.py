"""
tools/spots_weather_tool.py is v2, backed by OpenStreetMap (Nominatim +
Overpass, free, keyless, but real network calls, and Overpass's public
server has been observed to be slow/flaky under load). Gated behind
RUN_LIVE_PLACES_TESTS=1 to keep the default suite fast and independent
of that:
    RUN_LIVE_PLACES_TESTS=1 pytest tests/test_spots_weather_tool.py -v
"""

import os

import pytest

import tools.spots_weather_tool as spots_weather_tool_module
from tools.spots_weather_tool import search_destinations

live_only = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PLACES_TESTS") != "1",
    reason="live network call (Nominatim + Overpass) -- set RUN_LIVE_PLACES_TESTS=1 to run",
)


def test_search_destinations_caches_repeated_identical_calls(monkeypatch):
    search_destinations.cache_clear()
    calls = {"n": 0}

    def fake_geocode(city, country=None):
        calls["n"] += 1
        return (48.8566, 2.3522)

    monkeypatch.setattr(spots_weather_tool_module, "geocode_city", fake_geocode)
    monkeypatch.setattr(spots_weather_tool_module, "search_places_by_coords", lambda *a, **k: [])

    search_destinations("Paris", "France", limit=5)
    search_destinations("Paris", "France", limit=5)

    assert calls["n"] == 1


@live_only
def test_returns_real_named_places():
    results = search_destinations("Paris", "France", limit=5)
    assert results
    assert all(r["Destination Name"] for r in results)  # every result has a real name
    assert all("Destination Name" in r and "Type" in r for r in results)


@live_only
def test_results_sorted_closest_first():
    results = search_destinations("Paris", "France", limit=10)
    distances = [r["DistanceFromCenterKm"] for r in results]
    assert distances == sorted(distances)


@live_only
def test_unknown_city_returns_empty_list():
    assert search_destinations("Nonexistentcityxyz123") == []


@live_only
def test_season_match_and_climate_present_when_travel_month_given():
    results = search_destinations("Paris", "France", travel_month="April", limit=5)
    assert results
    assert all("season_match" in r and "climate" in r for r in results)


@live_only
def test_season_match_absent_without_travel_month():
    results = search_destinations("Paris", "France", limit=5)
    assert results
    assert all("season_match" not in r for r in results)


@live_only
def test_category_filter():
    results = search_destinations("Paris", "France", category="Museum", limit=10)
    assert results
    assert all(r["Type"] == "Museum" for r in results)
