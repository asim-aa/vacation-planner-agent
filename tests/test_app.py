"""
UI-level tests for app.py using Streamlit's official testing framework
(streamlit.testing.v1.AppTest), which runs the real script in a
simulated runtime and lets us click buttons / submit chat input without
a real browser.

Pre-seeding `at.session_state["trip_state"]` before `at.run()` bypasses
plan_trip() entirely (no live network calls, no LLM) -- these tests only
exercise app.py's own rendering and refine-button/chat logic, which was
otherwise only ever checked manually in a real browser this session.
Anywhere a refine action runs (which calls agents.*.get_llm() with no
override), agents.<agent>.get_llm is patched with a FakeLLM so no real
LLM endpoint is required.
"""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tests.fake_llm import FakeLLM

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _base_state(**overrides) -> dict:
    state = {
        "destination_city": "Paris",
        "destination_country": "France",
        "travel_month": "April",
        "duration_days": 6,
        "budget_total": 2500.0,
        "total_cost_estimate": 1000.0,
        "seat_class": "Economy",
        "flight_results": [{
            "Airline": "Delta", "Departure_Airport": "JFK", "Arrival_Airport": "CDG",
            "Seat_Class": "Economy", "Price_USD": 300.0, "Departure_Time": "2027-04-15 10:00",
            "Arrival_Time": "2027-04-15 22:00", "Stops": 0,
        }],
        "flight_recommendation": "Great flight!",
        "flight_cost_estimate": 600.0,
        "hotel_results": [{
            "HotelName": "Test Hotel", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
            "GuestRating": 4.5, "Amenities": ["Wifi"], "URL": "http://example.com",
        }],
        "hotel_recommendation": "Great hotel!",
        "lodging_cost_estimate": 480.0,
        "spot_results": [{
            "Destination Name": "Eiffel Tower", "Type": "Attraction", "EstimatedCostUSD": 15.0,
            "DistanceFromCenterKm": 1.0, "season_match": True, "Notable": True,
        }],
        "spot_recommendation": "Great spot!",
        "activities_cost_estimate": 90.0,
        "itinerary_markdown": "# Test itinerary",
    }
    state.update(overrides)
    return state


def _run_with(state: dict) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["trip_state"] = state
    at.run()
    return at


def test_app_loads_without_error():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    assert at.button[0].label == "✈️ Plan my trip"


def test_itinerary_renders_expected_structure():
    at = _run_with(_base_state())
    assert not at.exception
    assert at.header[0].value == "🗺️ Paris, France"
    assert [t.label for t in at.tabs] == ["✈️ Flights", "🏨 Lodging", "🎡 Activities", "📅 Day-by-Day", "💵 Budget"]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["📅 Duration"] == "6 days"
    assert metrics["💰 Budget"] == "$2,500"
    assert metrics["🧾 Estimated total"] == "$1,000"


def test_hotel_table_with_missing_rating_renders_without_error():
    # Regression test: mixing a float GuestRating with the string "--"
    # in one pandas column broke pyarrow serialization (a real bug hit
    # while testing live). GuestRating=None must render cleanly instead.
    state = _base_state(hotel_results=[
        {"HotelName": "Cheap Hotel", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
         "GuestRating": 3.5, "Amenities": [], "URL": "http://x.com"},
        {"HotelName": "Unrated Hotel", "cityName": "Paris", "EstimatedPriceUSD": 90.0,
         "GuestRating": None, "Amenities": [], "URL": "http://y.com"},
    ])
    at = _run_with(state)
    assert not at.exception
    assert len(at.dataframe) >= 1


def test_hotel_refine_button_switches_to_better_rated_hotel():
    state = _base_state(
        hotel_results=[
            {"HotelName": "Cheap Hotel", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
             "GuestRating": 3.5, "Amenities": [], "URL": "http://x.com"},
            {"HotelName": "Nice Hotel", "cityName": "Paris", "EstimatedPriceUSD": 150.0,
             "GuestRating": 4.8, "Amenities": [], "URL": "http://y.com"},
        ],
        max_nightly_hotel_price=200.0,
    )
    at = _run_with(state)
    hotel_buttons = [b for b in at.button if "better-rated" in b.label]
    assert len(hotel_buttons) == 1

    with patch("agents.hotel_agent.get_llm", return_value=FakeLLM("Nice Hotel is great!")):
        hotel_buttons[0].click().run()

    assert not at.exception
    assert at.session_state["trip_state"]["hotel_results"][0]["HotelName"] == "Nice Hotel"


def test_hotel_refine_button_absent_when_already_optimal():
    state = _base_state(
        hotel_results=[
            {"HotelName": "Only Hotel", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
             "GuestRating": 4.5, "Amenities": [], "URL": "http://x.com"},
        ],
        max_nightly_hotel_price=81.0,  # trivial headroom
    )
    at = _run_with(state)
    assert not [b for b in at.button if "better-rated" in b.label]


def test_flight_refine_button_switches_to_fewer_stops():
    state = _base_state(
        flight_results=[
            {"Airline": "Cheap Multi-Stop", "Departure_Airport": "JFK", "Arrival_Airport": "CDG",
             "Seat_Class": "Economy", "Price_USD": 300.0, "Departure_Time": "t1", "Arrival_Time": "t2", "Stops": 2},
            {"Airline": "Direct Flight", "Departure_Airport": "JFK", "Arrival_Airport": "CDG",
             "Seat_Class": "Economy", "Price_USD": 500.0, "Departure_Time": "t3", "Arrival_Time": "t4", "Stops": 0},
        ],
        lodging_cost_estimate=100.0,
        activities_cost_estimate=0.0,
        budget_total=2500.0,  # plenty of headroom for the pricier direct flight
    )
    at = _run_with(state)
    flight_buttons = [b for b in at.button if "more direct" in b.label]
    assert len(flight_buttons) == 1

    with patch("agents.flight_agent.get_llm", return_value=FakeLLM("Direct Flight is great!")):
        flight_buttons[0].click().run()

    assert not at.exception
    assert at.session_state["trip_state"]["flight_results"][0]["Airline"] == "Direct Flight"


def test_activities_refine_button_prefers_notable_spots():
    state = _base_state(spot_results=[
        {"Destination Name": "Obscure Plaza", "Type": "Attraction", "EstimatedCostUSD": 0.0,
         "DistanceFromCenterKm": 0.2, "season_match": True, "Notable": False},
        {"Destination Name": "Famous Landmark", "Type": "Museum", "EstimatedCostUSD": 15.0,
         "DistanceFromCenterKm": 1.5, "season_match": True, "Notable": True},
    ])
    at = _run_with(state)
    notable_buttons = [b for b in at.button if "well-known" in b.label]
    assert len(notable_buttons) == 1

    with patch("agents.spots_weather_agent.get_llm", return_value=FakeLLM("Famous Landmark is iconic!")):
        notable_buttons[0].click().run()

    assert not at.exception
    assert at.session_state["trip_state"]["spot_results"][0]["Destination Name"] == "Famous Landmark"


def test_chat_hotel_keyword_updates_state_and_replies_honestly():
    state = _base_state(hotel_results=[
        {"HotelName": "Cheap Hotel", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
         "GuestRating": 3.5, "Amenities": [], "URL": "http://x.com"},
        {"HotelName": "Nice Hotel", "cityName": "Paris", "EstimatedPriceUSD": 150.0,
         "GuestRating": 4.8, "Amenities": [], "URL": "http://y.com"},
    ])
    at = _run_with(state)

    with patch("agents.hotel_agent.get_llm", return_value=FakeLLM("Nice Hotel is great!")):
        at.chat_input[0].set_value("spend the rest on a nicer hotel").run()

    assert not at.exception
    history = at.session_state["chat_history"]
    assert history[0] == {"role": "user", "content": "spend the rest on a nicer hotel"}
    assert "Nice Hotel" in history[1]["content"]
    assert at.session_state["trip_state"]["hotel_results"][0]["HotelName"] == "Nice Hotel"


def test_chat_gives_honest_no_change_reply_when_nothing_better_exists():
    # Regression test for a real bug: a hub-stitched self-connect route
    # has only ONE flight candidate, so "get me a more direct flight"
    # had nothing to switch to, but used to still claim "Done -- switched
    # to X" anyway. It must now say there's nothing better instead.
    state = _base_state(flight_results=[{
        "Airline": "American + Asiana Airlines (self-connect via LAX)",
        "Departure_Airport": "SJC", "Arrival_Airport": "CAN", "Seat_Class": "Economy",
        "Price_USD": 754.0, "Departure_Time": "2027-04-15 06:10", "Arrival_Time": "2027-04-17 11:30",
        "Stops": 3, "SelfConnectedVia": "LAX",
    }])
    at = _run_with(state)

    with patch("agents.flight_agent.get_llm", return_value=FakeLLM("irrelevant")):
        at.chat_input[0].set_value("get me a more direct flight").run()

    assert not at.exception
    reply = at.session_state["chat_history"][1]["content"]
    assert "Done" not in reply
    assert "already the best" in reply
    assert "edit the trip request box" in reply


def test_chat_unclear_request_does_not_change_state():
    # "make this trip amazing somehow" has no hotel/flight/activities
    # keyword, so classify_followup falls back to an LLM call -- mocked
    # here to return something outside the valid category set.
    state = _base_state()
    at = _run_with(state)
    original_flight = at.session_state["trip_state"]["flight_results"][0]["Airline"]

    with patch("agents.followup_router.get_llm", return_value=FakeLLM("sure, anything!")):
        at.chat_input[0].set_value("make this trip amazing somehow").run()

    assert not at.exception
    reply = at.session_state["chat_history"][1]["content"]
    assert "I can currently help with" in reply
    assert at.session_state["trip_state"]["flight_results"][0]["Airline"] == original_flight
