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


def test_season_match_uses_real_climate_not_mock_best_season_column():
    # v2: season_match comes from one real historical-climate lookup per
    # country+month (tools/weather_tool.py), applied uniformly -- not from
    # the mock "Best Season" column, which varies randomly per row and is
    # no longer consulted for this.
    results = search_destinations("Japan", travel_month="January", limit=10)
    assert results
    season_matches = {r["season_match"] for r in results}
    assert len(season_matches) == 1  # same real climate answer for every row

    best_seasons = {r["Best Season"] for r in results}
    assert len(best_seasons) > 1  # sanity check: the mock column is per-row noise


def test_climate_field_present_and_reflects_reality_when_travel_month_given():
    # Cairo in July is genuinely very hot -- a real API should say unsuitable.
    results = search_destinations("Egypt", travel_month="July", limit=5)
    assert results
    assert all("climate" in r for r in results)
    assert all(r["climate"]["suitable"] is False for r in results)
    assert all(r["climate"]["avg_max_temp_c"] > 32 for r in results)


def test_climate_field_absent_without_travel_month():
    results = search_destinations("Japan", limit=5)
    assert results
    assert all("climate" not in r for r in results)
