"""
narrative_guard.py is pure/offline (airportsdata is a local file, no
network) so it's tested directly.
"""

from agents.narrative_guard import city_for_airport_code, mentions_unexpected_city


def test_city_for_airport_code_known_code():
    assert city_for_airport_code("CDG") == "Paris"


def test_city_for_airport_code_unknown_code_returns_none():
    assert city_for_airport_code("ZZZ") is None


def test_city_for_airport_code_none_input_returns_none():
    assert city_for_airport_code(None) is None


def test_flags_real_city_not_in_allowed_set():
    # The actual hallucination this guard exists to catch.
    text = "This flight is a practical choice for reaching Vancouver from San Jose."
    assert mentions_unexpected_city(text, allowed_names={"San Jose", "Guangzhou"}) is True


def test_does_not_flag_cities_that_are_allowed():
    text = "This flight departs San Jose and arrives in Guangzhou, a great deal."
    assert mentions_unexpected_city(text, allowed_names={"San Jose", "Guangzhou"}) is False


def test_does_not_flag_airline_name_that_collides_with_a_real_city():
    # Verified live: "Delta" is both a major US airline and a real town
    # with its own airport -- must not false-positive when the airline
    # name is in the allowed set.
    text = "Take the Delta flight from JFK to CDG for $306."
    assert mentions_unexpected_city(text, allowed_names={"New York", "Paris", "Delta"}) is False


def test_flags_airline_name_collision_when_not_allowed():
    text = "Take the Delta flight from JFK to CDG for $306."
    assert mentions_unexpected_city(text, allowed_names={"New York", "Paris"}) is True


def test_does_not_flag_non_city_proper_nouns():
    text = "Icelandair offers a comfortable, affordable Economy option."
    assert mentions_unexpected_city(text, allowed_names={"New York", "Paris"}) is False


def test_multi_word_city_recognized_as_allowed():
    text = "Enjoy your stay in New York before heading home."
    assert mentions_unexpected_city(text, allowed_names={"New York"}) is False
