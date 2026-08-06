from agents.compile_itinerary import compile_itinerary_node


def _base_state(**overrides):
    state = {
        "destination_city": "Paris",
        "destination_country": "France",
        "travel_month": "April",
        "duration_days": 4,
        "budget_total": 1000.0,
        "flight_cost_estimate": 100.0,
        "lodging_cost_estimate": 200.0,
        "activities_cost_estimate": 300.0,
        "hotel_results": [{"HotelName": "Hotel A"}],
        "hotel_recommendation": "Hotel A is great.",
        "spot_results": [
            {"Destination Name": "Spot 1"},
            {"Destination Name": "Spot 2"},
        ],
        "spot_recommendation": "Visit Spot 1 and Spot 2.",
        "flight_recommendation": "Fly Delta.",
    }
    state.update(overrides)
    return state


def test_total_cost_sums_all_three_categories():
    result = compile_itinerary_node(_base_state())
    assert result["total_cost_estimate"] == 600.0


def test_within_budget_status():
    result = compile_itinerary_node(_base_state())
    assert "Within budget" in result["itinerary_markdown"]


def test_over_budget_status_reported_not_hidden():
    state = _base_state(budget_total=100.0)
    result = compile_itinerary_node(state)
    assert "Over budget" in result["itinerary_markdown"]
    assert "$500.00" in result["itinerary_markdown"]  # 600 total - 100 budget


def test_itinerary_days_match_spot_results_order():
    result = compile_itinerary_node(_base_state())
    # Scope to the itinerary section -- spot names also legitimately appear
    # earlier, in the Activities recommendation narrative.
    itinerary_section = result["itinerary_markdown"].split("## Chronological Itinerary")[1]
    day2_index = itinerary_section.index("Day 2")
    day3_index = itinerary_section.index("Day 3")
    spot1_index = itinerary_section.index("Spot 1")
    spot2_index = itinerary_section.index("Spot 2")
    assert day2_index < spot1_index < day3_index < spot2_index


def test_hotel_name_matches_between_recommendation_and_itinerary():
    result = compile_itinerary_node(_base_state())
    markdown = result["itinerary_markdown"]
    assert "Hotel A is great." in markdown
    assert "check into Hotel A" in markdown


def test_missing_spots_fills_free_days_without_skipping_day_numbers():
    state = _base_state(spot_results=[], duration_days=5)
    result = compile_itinerary_node(state)
    markdown = result["itinerary_markdown"]
    for day in range(1, 6):
        assert f"Day {day}" in markdown


def test_single_day_trip_does_not_crash():
    state = _base_state(duration_days=1)
    result = compile_itinerary_node(state)
    assert "Day 1" in result["itinerary_markdown"]


def test_missing_hotel_shows_placeholder_not_crash():
    state = _base_state(hotel_results=[])
    result = compile_itinerary_node(state)
    assert "TBD" in result["itinerary_markdown"]
