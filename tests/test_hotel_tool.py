from tools.hotel_tool import search_hotels


def test_filters_by_city():
    results = search_hotels("Paris", limit=5)
    assert results
    assert all(r["cityName"].lower() == "paris" for r in results)


def test_filters_by_max_price():
    results = search_hotels("Paris", max_price=100, limit=10)
    assert results
    assert all(r["EstimatedPriceUSD"] <= 100 for r in results)


def test_results_sorted_cheapest_first():
    results = search_hotels("Paris", limit=10)
    prices = [r["EstimatedPriceUSD"] for r in results]
    assert prices == sorted(prices)


def test_unknown_city_returns_empty_list():
    assert search_hotels("Nonexistentville") == []


def test_us_city_matches_state_suffixed_rows():
    # Hotels for US cities are stored as "Atlanta,   Georgia", not "Atlanta".
    results = search_hotels("Atlanta", limit=5)
    assert results
    assert all("Atlanta" in r["cityName"] for r in results)


def test_min_rating_filter():
    results = search_hotels("Paris", min_rating="FiveStar", limit=10)
    assert results
    assert all(r["HotelRating"] == "FiveStar" for r in results)
