from tools.flight_tool import get_baseline_price, search_flights


def test_filters_by_route():
    results = search_flights("JFK", "ATL", limit=10)
    assert results
    assert all(r["Departure_Airport"] == "JFK" and r["Arrival_Airport"] == "ATL" for r in results)


def test_filters_by_seat_class():
    results = search_flights("JFK", "ATL", seat_class="Economy", limit=10)
    assert results
    assert all(r["Seat_Class"] == "Economy" for r in results)


def test_results_sorted_cheapest_first():
    results = search_flights("JFK", "ATL", limit=10)
    prices = [r["Price_USD"] for r in results]
    assert prices == sorted(prices)


def test_unknown_route_returns_empty_list():
    assert search_flights("XXX", "YYY") == []


def test_max_price_filter():
    results = search_flights("JFK", "ATL", max_price=150, limit=10)
    assert results
    assert all(r["Price_USD"] <= 150 for r in results)


def test_baseline_price_is_average_for_route_and_class():
    baseline = get_baseline_price("JFK", "ATL", seat_class="Economy")
    assert baseline is not None
    assert baseline > 0


def test_baseline_price_none_for_unknown_route():
    assert get_baseline_price("XXX", "YYY") is None
