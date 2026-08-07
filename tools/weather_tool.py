"""
Weather tool -- v2: real climate data via Open-Meteo (free, keyless, no
rate-limit concerns), replacing the mock "Best Season" column that used to
drive season_match in spots_weather_tool.py.

Methodology and its limits (stated plainly, not hidden):
  - Open-Meteo's forecast API only covers ~16 days ahead, so a real
    forecast for an arbitrary future travel month isn't possible. Instead
    this queries Open-Meteo's free Historical Weather (Archive) API for
    the same calendar month one year ago, as a proxy for "typical"
    conditions in that month. It is a real-data proxy, not a guarantee --
    a single past year is not a multi-year climate normal.
  - The destinations dataset only has a Country field, not per-destination
    coordinates (the "Destination Name" values are generic templates, not
    real places -- see spots_weather_tool.py). So this checks climate at
    one representative city per country, not the specific destination.
    COUNTRY_REFERENCE_CITY documents which city stands in for each.
  - "Suitable" is a simple heuristic (comfortable temperature range, low
    average precipitation), not a rigorous climate classification.
"""

from calendar import monthrange
from datetime import date

import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# One representative (usually the most touristed) city per supported
# country, since the destinations dataset only has country-level location.
COUNTRY_REFERENCE_CITY = {
    "Argentina": {"city": "Buenos Aires", "lat": -34.6037, "lon": -58.3816},
    "Australia": {"city": "Sydney", "lat": -33.8688, "lon": 151.2093},
    "Brazil": {"city": "Rio de Janeiro", "lat": -22.9068, "lon": -43.1729},
    "Canada": {"city": "Toronto", "lat": 43.6532, "lon": -79.3832},
    "China": {"city": "Beijing", "lat": 39.9042, "lon": 116.4074},
    "Egypt": {"city": "Cairo", "lat": 30.0444, "lon": 31.2357},
    "France": {"city": "Paris", "lat": 48.8566, "lon": 2.3522},
    "Germany": {"city": "Berlin", "lat": 52.5200, "lon": 13.4050},
    "Greece": {"city": "Athens", "lat": 37.9838, "lon": 23.7275},
    "India": {"city": "New Delhi", "lat": 28.6139, "lon": 77.2090},
    "Italy": {"city": "Rome", "lat": 41.9028, "lon": 12.4964},
    "Japan": {"city": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    "Kenya": {"city": "Nairobi", "lat": -1.2921, "lon": 36.8219},
    "Mexico": {"city": "Mexico City", "lat": 19.4326, "lon": -99.1332},
    "Morocco": {"city": "Marrakech", "lat": 31.6295, "lon": -7.9811},
    "New Zealand": {"city": "Auckland", "lat": -36.8485, "lon": 174.7633},
    "Peru": {"city": "Lima", "lat": -12.0464, "lon": -77.0428},
    "South Africa": {"city": "Cape Town", "lat": -33.9249, "lon": 18.4241},
    "Spain": {"city": "Madrid", "lat": 40.4168, "lon": -3.7038},
    "Thailand": {"city": "Bangkok", "lat": 13.7563, "lon": 100.5018},
    "USA": {"city": "Washington, DC", "lat": 38.9072, "lon": -77.0369},
    "Vietnam": {"city": "Hanoi", "lat": 21.0285, "lon": 105.8542},
}

MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# Heuristic comfort thresholds -- a simplification, documented as such.
COMFORTABLE_MAX_TEMP_RANGE_C = (15, 32)
MAX_COMFORTABLE_DAILY_PRECIP_MM = 6.0


def get_climate_suitability(country: str, month_name: str) -> dict | None:
    """Return real historical climate data for `country`'s reference city
    in `month_name`, plus a heuristic `suitable` bool. Returns None if the
    country has no reference city mapped, or the API call fails.
    """
    ref = COUNTRY_REFERENCE_CITY.get(country)
    month_num = MONTH_NUMBERS.get(month_name.strip().lower())
    if not ref or not month_num:
        return None

    today = date.today()
    year = today.year - 1 if month_num <= today.month else today.year - 2
    last_day = monthrange(year, month_num)[1]
    start_date = date(year, month_num, 1).isoformat()
    end_date = date(year, month_num, last_day).isoformat()

    resp = requests.get(
        ARCHIVE_URL,
        params={
            "latitude": ref["lat"],
            "longitude": ref["lon"],
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,precipitation_sum",
            "timezone": "auto",
        },
        timeout=20,
    )
    if resp.status_code != 200:
        return None

    daily = resp.json().get("daily", {})
    max_temps = [t for t in daily.get("temperature_2m_max", []) if t is not None]
    precip = [p for p in daily.get("precipitation_sum", []) if p is not None]
    if not max_temps:
        return None

    avg_max_temp_c = round(sum(max_temps) / len(max_temps), 1)
    avg_precip_mm = round(sum(precip) / len(precip), 1) if precip else 0.0

    lo, hi = COMFORTABLE_MAX_TEMP_RANGE_C
    suitable = lo <= avg_max_temp_c <= hi and avg_precip_mm <= MAX_COMFORTABLE_DAILY_PRECIP_MM

    return {
        "reference_city": ref["city"],
        "reference_year": year,
        "avg_max_temp_c": avg_max_temp_c,
        "avg_daily_precip_mm": avg_precip_mm,
        "suitable": suitable,
    }


if __name__ == "__main__":
    for country, month in [("Japan", "April"), ("Egypt", "July"), ("Thailand", "October")]:
        print(country, month, "->", get_climate_suitability(country, month))
