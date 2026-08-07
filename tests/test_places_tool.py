"""Offline tests for the pure-logic parts of tools/places_tool.py. Network
calls (geocode_city, search_places*) are exercised via
tests/test_spots_weather_tool.py's live-gated tests instead."""

from tools.places_tool import _haversine_km


def test_haversine_zero_distance_for_same_point():
    assert _haversine_km(48.8566, 2.3522, 48.8566, 2.3522) == 0.0


def test_haversine_known_distance_paris_to_london():
    # Paris to London is roughly 340km as the crow flies.
    km = _haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert 330 < km < 350
