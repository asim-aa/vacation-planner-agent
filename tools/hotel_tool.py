"""
Hotel Agent tool -- v2: live hotel search via fast-hotels (scrapes Google
Hotels, no API key, no formal quota), replacing the v1 mock dataset and
its synthetic (rating-derived) pricing.

Note: unlike the mock version, this needs real checkin/checkout dates --
see agents/hotel_agent.py, which derives them from the trip's
travel_month via agents/date_utils.py.
"""

from fast_hotels import get_hotels
from fast_hotels.hotels_impl import Guests, HotelData

# No real hotel costs this little per night -- seen in practice: the
# scraper occasionally returns a parsing artifact (e.g. a stray
# "Copyright The Closure Library Authors." string pulled from page JS)
# as if it were a $1/night hotel. Filtering below this floor is a cheap,
# justified guard against that class of garbage without trying to
# validate hotel names generally.
MIN_PLAUSIBLE_NIGHTLY_PRICE = 10.0


def search_hotels(
    city: str,
    checkin_date: str,
    checkout_date: str,
    max_price: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return live hotel options in `city` for the given checkin/checkout
    dates (YYYY-MM-DD), optionally capped at `max_price` per night,
    cheapest first.

    Returns an empty list on no results or any scrape failure -- callers
    must handle that without crashing.
    """
    try:
        result = get_hotels(
            hotel_data=[HotelData(checkin_date=checkin_date, checkout_date=checkout_date, location=city)],
            guests=Guests(adults=1),
            fetch_mode="common",
            limit=limit * 2,  # fetch extra headroom in case max_price trims some out
        )
    except Exception:
        return []

    results = [
        {
            "HotelName": h.name,
            "cityName": city,
            "EstimatedPriceUSD": h.price,
            "GuestRating": h.rating,
            "Amenities": h.amenities or [],
            "URL": h.url,
        }
        for h in (result.hotels or [])
        if h.price is not None and h.price >= MIN_PLAUSIBLE_NIGHTLY_PRICE
    ]

    if max_price is not None:
        results = [r for r in results if r["EstimatedPriceUSD"] <= max_price]

    results.sort(key=lambda r: r["EstimatedPriceUSD"])
    return results[:limit]


if __name__ == "__main__":
    for hotel in search_hotels("Paris", "2026-09-15", "2026-09-18", max_price=150, limit=5):
        print(hotel)
    print("No-match test:", search_hotels("Nowhereland1234", "2026-09-15", "2026-09-18"))
