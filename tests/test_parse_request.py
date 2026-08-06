from agents.parse_request import parse_request_node
from tests.fake_llm import FakeLLM


def test_parses_well_formed_json_response():
    llm = FakeLLM("""
    {
        "destination_city": "Paris",
        "destination_country": "France",
        "travel_month": "April",
        "budget_total": 2500,
        "duration_days": 6,
        "origin_airport": "JFK",
        "destination_airport": null,
        "seat_class": "Economy"
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["destination_city"] == "Paris"
    assert result["destination_country"] == "France"
    assert result["budget_total"] == 2500.0
    assert result["duration_days"] == 6
    assert result["origin_airport"] == "JFK"
    assert result["destination_airport"] is None
    assert result["seat_class"] == "Economy"


def test_invalid_airport_codes_fall_back_to_defaults():
    llm = FakeLLM("""
    {
        "destination_city": "Atlanta",
        "destination_country": "USA",
        "budget_total": 1000,
        "duration_days": 3,
        "origin_airport": "NOT_REAL",
        "destination_airport": "ALSO_NOT_REAL"
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["origin_airport"] == "JFK"  # invalid -> default
    assert result["destination_airport"] is None  # invalid -> None, not passed through


def test_valid_destination_airport_is_kept():
    llm = FakeLLM("""
    {
        "destination_city": "Atlanta",
        "destination_country": "USA",
        "budget_total": 1000,
        "duration_days": 3,
        "origin_airport": "JFK",
        "destination_airport": "ATL"
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["destination_airport"] == "ATL"


def test_extracts_json_even_with_surrounding_prose():
    llm = FakeLLM(
        'Here is the JSON you asked for:\n'
        '{"destination_city": "Tokyo", "destination_country": "Japan", '
        '"budget_total": 3000, "duration_days": 5, "origin_airport": "LAX", '
        '"destination_airport": null}\n'
        "Let me know if you need anything else!"
    )
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["destination_city"] == "Tokyo"
    assert result["budget_total"] == 3000.0
