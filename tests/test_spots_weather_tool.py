from tools.spots_weather_tool import search_destinations


def test_filters_by_country():
    results = search_destinations("Japan", limit=10)
    assert results
    assert all(r["Country"] == "Japan" for r in results)


def test_filters_by_category():
    results = search_destinations("Japan", category="Historical", limit=10)
    assert results
    assert all(r["Type"] == "Historical" for r in results)


def test_unknown_country_returns_empty_list():
    assert search_destinations("Nowhereland") == []


def test_season_match_flag_set_when_travel_month_given():
    results = search_destinations("Japan", travel_month="April", limit=10)
    assert results
    assert all("season_match" in r for r in results)
    assert all(isinstance(r["season_match"], bool) for r in results)


def test_season_match_absent_without_travel_month():
    results = search_destinations("Japan", limit=10)
    assert results
    assert all("season_match" not in r for r in results)


def test_season_match_reflects_best_season():
    results = search_destinations("Japan", travel_month="January", limit=10)
    for r in results:
        assert r["season_match"] == (r["Best Season"] == "Winter")
