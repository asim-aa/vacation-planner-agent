from agents.budget import MIN_NIGHTLY_HOTEL_PRICE, compute_hotel_budget_node


def test_splits_remaining_budget_across_nights():
    state = {
        "budget_total": 1000.0,
        "duration_days": 5,
        "flight_cost_estimate": 200.0,
        "activities_cost_estimate": 300.0,
    }
    # remaining = 1000 - 200 - 300 = 500; 500 / 5 nights = 100/night
    result = compute_hotel_budget_node(state)
    assert result["max_nightly_hotel_price"] == 100.0


def test_clamps_to_minimum_when_budget_is_tight():
    state = {
        "budget_total": 100.0,
        "duration_days": 5,
        "flight_cost_estimate": 200.0,
        "activities_cost_estimate": 300.0,
    }
    # remaining would be negative -- clamp to the floor instead
    result = compute_hotel_budget_node(state)
    assert result["max_nightly_hotel_price"] == MIN_NIGHTLY_HOTEL_PRICE


def test_defaults_missing_cost_estimates_to_zero():
    state = {"budget_total": 500.0, "duration_days": 5}
    result = compute_hotel_budget_node(state)
    assert result["max_nightly_hotel_price"] == 100.0
