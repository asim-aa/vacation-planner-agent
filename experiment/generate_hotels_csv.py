"""
One-off generator for experiment/data/hotels.csv.

The flights CSV (experiment/data/flights.csv) is the source of truth for
which cities are supported -- this reads the exact same 10 airport codes
from it rather than hardcoding a separate list that could drift out of
sync.

Each city gets exactly 3 hotels: cheap, mid, expensive. Prices are
hand-set (not randomized) so they're reproducible and so the spacing
between tiers is deliberate -- roughly 1.8x cheap->mid and 3.2x
cheap->expensive, consistently, so upgrade-cost math produces
meaningfully different numbers per tier rather than near-ties.
"""

import csv
from pathlib import Path

import pandas as pd

FLIGHTS_PATH = Path(__file__).parent / "data" / "flights.csv"
HOTELS_PATH = Path(__file__).parent / "data" / "hotels.csv"

CITY_NAMES = {
    "DFW": "Dallas",
    "LAX": "Los Angeles",
    "PHX": "Phoenix",
    "SFO": "San Francisco",
    "MCO": "Orlando",
    "DEN": "Denver",
    "MIA": "Miami",
    "JFK": "New York",
    "ORD": "Chicago",
    "BOS": "Boston",
}

# Cheap-tier base price per city (reflects realistic relative cost of
# living -- SF/NYC/LA priciest, PHX/DFW/DEN cheapest) -- mid and
# expensive are then a fixed multiple of it, kept consistent across
# every city so the spacing logic is uniform and easy to reason about.
CHEAP_BASE = {
    "PHX": 75, "DFW": 80, "DEN": 85, "BOS": 90, "MCO": 95,
    "ORD": 100, "MIA": 120, "LAX": 130, "JFK": 140, "SFO": 150,
}
MID_MULTIPLIER = 1.85
EXPENSIVE_MULTIPLIER = 3.25

TIER_LABELS = {
    "cheap": "Budget Inn",
    "mid": "Plaza Hotel",
    "expensive": "Grand Resort & Spa",
}


def main() -> None:
    airports = sorted(
        set(pd.read_csv(FLIGHTS_PATH)["Departure_Airport"]) | set(pd.read_csv(FLIGHTS_PATH)["Arrival_Airport"])
    )
    assert set(airports) == set(CITY_NAMES), f"City list drifted from flights.csv: {airports}"

    rows = []
    hotel_id = 1
    for code in airports:
        city_name = CITY_NAMES[code]
        cheap_price = CHEAP_BASE[code]
        mid_price = round(cheap_price * MID_MULTIPLIER)
        expensive_price = round(cheap_price * EXPENSIVE_MULTIPLIER)

        for tier, price in (("cheap", cheap_price), ("mid", mid_price), ("expensive", expensive_price)):
            rows.append({
                "Hotel_ID": f"HT{1000 + hotel_id}",
                "City": code,
                "Hotel_Name": f"{city_name} {TIER_LABELS[tier]}",
                "Hotel_Tier": tier,
                "Hotel_Price": price,
            })
            hotel_id += 1

    with open(HOTELS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Hotel_ID", "City", "Hotel_Name", "Hotel_Tier", "Hotel_Price"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} hotels ({len(airports)} cities x 3 tiers) to {HOTELS_PATH}")


if __name__ == "__main__":
    main()
