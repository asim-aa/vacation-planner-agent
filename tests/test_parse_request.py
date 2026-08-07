from agents.parse_request import parse_request_node
from tests.fake_llm import FakeLLM


def test_parses_well_formed_json_response():
    llm = FakeLLM("""
    {
        "destination_city": "Paris",
        "destination_country": "France",
        "origin_city": "New York",
        "origin_country": "USA",
        "travel_month": "April",
        "budget_total": 2500,
        "duration_days": 6,
        "seat_class": "Economy"
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["destination_city"] == "Paris"
    assert result["destination_country"] == "France"
    assert result["origin_city"] == "New York"
    assert result["origin_country"] == "USA"
    assert result["budget_total"] == 2500.0
    assert result["duration_days"] == 6
    assert result["seat_class"] == "Economy"


def test_origin_city_defaults_when_unstated():
    llm = FakeLLM("""
    {
        "destination_city": "Atlanta",
        "destination_country": "USA",
        "budget_total": 1000,
        "duration_days": 3
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["origin_city"] == "New York"  # default when unstated
    assert result["origin_country"] is None


def test_any_real_origin_city_is_kept_not_restricted_to_a_fixed_list():
    llm = FakeLLM("""
    {
        "destination_city": "Rome",
        "destination_country": "Italy",
        "origin_city": "Berlin",
        "origin_country": "Germany",
        "budget_total": 1000,
        "duration_days": 3
    }
    """)
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["origin_city"] == "Berlin"  # not one of the old 8 US airports


def test_extracts_json_even_with_surrounding_prose():
    llm = FakeLLM(
        'Here is the JSON you asked for:\n'
        '{"destination_city": "Tokyo", "destination_country": "Japan", '
        '"origin_city": "Los Angeles", '
        '"budget_total": 3000, "duration_days": 5}\n'
        "Let me know if you need anything else!"
    )
    result = parse_request_node({"user_request": "anything"}, llm=llm)

    assert result["destination_city"] == "Tokyo"
    assert result["budget_total"] == 3000.0
