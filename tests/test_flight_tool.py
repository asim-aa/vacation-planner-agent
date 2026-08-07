"""
tools/flight_tool.py is v3, backed by fast-flights (scrapes Google
Flights, no API key, no formal quota) plus fully offline airport
resolution via airportsdata. resolve_city_to_iata() is pure local lookup
so it's tested directly; search_flights()/get_baseline_price() make a
real (free, unrestricted) network call, gated the same way the earlier
quota-limited tests were, in case Google ever rate-limits or blocks the
scraper -- keeps the default suite fast and independent of that.
"""

import json
import os

import pytest

import tools.flight_tool as flight_tool_module
from tools.flight_tool import (
    _nearest_hubs,
    get_baseline_price,
    resolve_city_to_iata,
    resolve_city_to_iata_candidates,
    search_flights,
    search_flights_via_hub,
    select_flight,
)

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


def test_resolve_city_to_iata_candidates_unknown_city_returns_empty_list():
    assert resolve_city_to_iata_candidates("Nowhereland") == []


def test_resolve_city_to_iata_candidates_jakarta_includes_both_hubs():
    # Regression test: Jakarta has two "International"-named airports
    # (CGK and HLP), so a single best-guess pick isn't reliable -- the
    # caller needs the full ranked list to fall back through.
    candidates = resolve_city_to_iata_candidates("Jakarta", "Indonesia")
    assert "CGK" in candidates
    assert "HLP" in candidates


def test_resolve_city_to_iata_returns_first_candidate():
    candidates = resolve_city_to_iata_candidates("Paris", "France")
    assert resolve_city_to_iata("Paris", "France") == candidates[0]


def test_get_baseline_price_averages_given_results():
    results = [
        {"Price_USD": 100.0},
        {"Price_USD": 200.0},
        {"Price_USD": 300.0},
    ]
    assert get_baseline_price(results) == 200.0


def test_get_baseline_price_empty_list_returns_none():
    assert get_baseline_price([]) is None


class _FakeAirport:
    def __init__(self, code):
        self.code = code


class _FakeDatetime:
    date = (2027, 4, 15)
    time = [10, 0]


class _FakeLeg:
    from_airport = _FakeAirport("JFK")
    to_airport = _FakeAirport("ATL")
    departure = _FakeDatetime()
    arrival = _FakeDatetime()


class _FakeFlight:
    airlines = ["Delta"]
    price = 100.0
    flights = [_FakeLeg()]


def test_search_flights_caches_repeated_identical_calls(monkeypatch):
    search_flights.cache_clear()
    calls = {"n": 0}

    def fake_get_flights(query):
        calls["n"] += 1
        return [_FakeFlight()]

    monkeypatch.setattr(flight_tool_module, "get_flights", fake_get_flights)
    monkeypatch.setattr(flight_tool_module, "create_query", lambda **k: object())

    search_flights("JFK", "ATL", "2027-04-15", limit=5)
    search_flights("JFK", "ATL", "2027-04-15", limit=5)

    assert calls["n"] == 1


FLIGHTS_BY_PRICE = [
    {"Airline": "Budget Air", "Price_USD": 200.0, "Stops": 2},
    {"Airline": "Mid Air", "Price_USD": 350.0, "Stops": 1},
    {"Airline": "Direct Air", "Price_USD": 500.0, "Stops": 0},
]


def test_select_flight_cheapest_returns_first_result():
    assert select_flight(FLIGHTS_BY_PRICE, optimize_for="cheapest") == FLIGHTS_BY_PRICE[0]


def test_select_flight_comfort_picks_fewest_stops_within_budget():
    # Direct Air (0 stops) is the most comfortable, but only Mid Air (1
    # stop) fits under this budget ceiling.
    picked = select_flight(FLIGHTS_BY_PRICE, optimize_for="comfort", max_price=400.0)
    assert picked["Airline"] == "Mid Air"


def test_select_flight_comfort_falls_back_to_cheapest_when_nothing_fits():
    picked = select_flight(FLIGHTS_BY_PRICE, optimize_for="comfort", max_price=50.0)
    assert picked == FLIGHTS_BY_PRICE[0]


def test_select_flight_comfort_ties_broken_by_price():
    tied = [
        {"Airline": "A", "Price_USD": 300.0, "Stops": 1},
        {"Airline": "B", "Price_USD": 250.0, "Stops": 1},
    ]
    assert select_flight(tied, optimize_for="comfort", max_price=1000.0)["Airline"] == "B"


def _fake_single_flight():
    sf = [None] * 22
    sf[3], sf[4] = "JFK", "John F Kennedy International Airport"
    sf[6], sf[5] = "CGK", "Soekarno-Hatta International Airport"
    sf[8], sf[10] = [10, 0], [22, 30]
    sf[11] = 1230
    sf[17] = "Boeing 777"
    sf[20], sf[21] = [2026, 10, 15], [2026, 10, 16]
    return sf


def _fake_flight_record(with_price):
    # Mirrors fast_flights' internal index-based payload shape (see
    # tools/_fast_flights_patch.py) -- flight[22] = extras, price = k[1].
    flight = [None] * 23
    flight[0] = "Nonstop"
    flight[1] = ["Garuda Indonesia"]
    flight[2] = [_fake_single_flight()]
    flight[22] = [None] * 9
    flight[22][7], flight[22][8] = 500, 550
    price = [[None, 850.0]] if with_price else []
    return [flight, price]


def test_fast_flights_patch_skips_price_less_record_without_dropping_valid_ones():
    # Regression test for a real upstream bug (fast-flights 3.0.2): one
    # itinerary in Google's response with no price attached used to crash
    # the parse of the ENTIRE response via an unhandled IndexError,
    # silently discarding every real flight alongside it. Verified live
    # on LAX->CGK, where this wiped out 3 real, bookable results.
    from fast_flights.parser import parse_js  # patched via tools._fast_flights_patch import

    payload = [None] * 8
    payload[3] = [[_fake_flight_record(with_price=False), _fake_flight_record(with_price=True)]]
    payload[7] = [None, [[], []]]
    js = "AF_initDataCallback({key: 'ds:1', data:" + json.dumps(payload) + ", sideChannel: {}});"

    results = parse_js(js)

    assert len(results) == 1
    assert results[0].price == 850.0


def test_fast_flights_patch_handles_payload_3_itself_being_none():
    # Regression test for a second upstream bug: fast-flights only guards
    # `payload[3][0] is None` (a legitimate "no results" shape) but not
    # `payload[3] is None` (also legitimate -- verified live on BOI->CGK),
    # which crashed with an unhandled TypeError instead of returning [].
    from fast_flights.parser import parse_js

    payload = [None] * 8
    payload[3] = None
    payload[7] = [None, [[], []]]
    js = "AF_initDataCallback({key: 'ds:1', data:" + json.dumps(payload) + ", sideChannel: {}});"

    assert parse_js(js) == []


def _fake_leg(price, airline, arrival_time, stops=0):
    return {
        "Airline": airline, "Departure_Airport": "X", "Arrival_Airport": "Y",
        "Seat_Class": "Economy", "Price_USD": price, "Departure_Time": "2026-10-15 05:00",
        "Arrival_Time": arrival_time, "Stops": stops,
    }


def test_nearest_hubs_excludes_given_codes_and_sorts_by_distance():
    hubs = _nearest_hubs("BOI", exclude={"BOI", "CGK"}, limit=3)
    assert "BOI" not in hubs
    assert "CGK" not in hubs
    assert len(hubs) == 3
    # Seattle is much closer to Boise than Dubai -- sanity check the ranking is real.
    all_hubs = _nearest_hubs("BOI", exclude={"BOI", "CGK"}, limit=len(flight_tool_module.MAJOR_HUBS))
    assert all_hubs.index("SEA") < all_hubs.index("DXB")


def test_search_flights_via_hub_combines_two_legs(monkeypatch):
    def fake_search_flights(origin, destination, departure_date, **kwargs):
        if destination in flight_tool_module.MAJOR_HUBS:
            return [_fake_leg(200.0, "Alaska", "2026-10-15 10:00")]
        return [_fake_leg(500.0, "Delta", "2026-10-16 08:00", stops=1)]

    monkeypatch.setattr(flight_tool_module, "search_flights", fake_search_flights)

    results = search_flights_via_hub("BOI", "CGK", "2026-10-15", seat_class="Economy")

    assert len(results) == 1
    combo = results[0]
    assert combo["Price_USD"] == 700.0
    assert combo["Stops"] == 2  # leg1 (0) + leg2 (1) + 1 for the self-connection itself
    assert combo["Departure_Airport"] == "BOI"
    assert combo["Arrival_Airport"] == "CGK"
    assert "SelfConnectedVia" in combo


def test_search_flights_via_hub_returns_empty_when_no_hub_works(monkeypatch):
    monkeypatch.setattr(flight_tool_module, "search_flights", lambda *a, **k: [])
    assert search_flights_via_hub("BOI", "CGK", "2026-10-15") == []


def test_search_flights_via_hub_uses_next_day_connection_after_late_arrival(monkeypatch):
    connect_dates = []

    def fake_search_flights(origin, destination, departure_date, **kwargs):
        if destination in flight_tool_module.MAJOR_HUBS:
            return [_fake_leg(200.0, "Alaska", "2026-10-15 23:30")]  # late arrival at hub
        connect_dates.append(departure_date)
        return [_fake_leg(500.0, "Delta", "2026-10-17 08:00")]

    monkeypatch.setattr(flight_tool_module, "search_flights", fake_search_flights)

    search_flights_via_hub("BOI", "CGK", "2026-10-15")

    assert connect_dates[0] == "2026-10-16"  # pushed a day for the overnight layover


@live_only
def test_live_search_flights_returns_real_results():
    results = search_flights("JFK", "ATL", "2026-09-15", limit=5)
    assert results
    prices = [r["Price_USD"] for r in results]
    assert prices == sorted(prices)


@live_only
def test_live_search_flights_unknown_route_returns_empty():
    assert search_flights("XXX", "YYY", "2026-09-15") == []
