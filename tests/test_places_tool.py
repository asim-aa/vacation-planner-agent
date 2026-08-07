"""Offline tests for the pure-logic parts of tools/places_tool.py. Live
network calls (geocode_city, the Overpass query itself) are exercised via
tests/test_spots_weather_tool.py's live-gated tests instead --
search_places_by_coords's own result-building logic is tested here by
monkeypatching _query_overpass with fake elements."""

import tools.places_tool as places_tool_module
from tools.places_tool import _haversine_km, search_places_by_coords


def test_haversine_zero_distance_for_same_point():
    assert _haversine_km(48.8566, 2.3522, 48.8566, 2.3522) == 0.0


def test_haversine_known_distance_paris_to_london():
    # Paris to London is roughly 340km as the crow flies.
    km = _haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert 330 < km < 350


def _fake_element(name, lat, lon, wikipedia=None, wikidata=None, fee=None):
    tags = {"name": name, "tourism": "museum"}
    if wikipedia:
        tags["wikipedia"] = wikipedia
    if wikidata:
        tags["wikidata"] = wikidata
    if fee:
        tags["fee"] = fee
    return {"lat": lat, "lon": lon, "tags": tags}


def test_notable_flag_true_when_wikipedia_or_wikidata_tag_present(monkeypatch):
    elements = [
        _fake_element("Famous Museum", 48.86, 2.35, wikipedia="en:Famous Museum"),
        _fake_element("Local Gallery", 48.861, 2.351),
    ]
    monkeypatch.setattr(places_tool_module, "_query_overpass", lambda *a, **k: elements)

    results = search_places_by_coords(48.8566, 2.3522)
    by_name = {r["Destination Name"]: r for r in results}

    assert by_name["Famous Museum"]["Notable"] is True
    assert by_name["Local Gallery"]["Notable"] is False
