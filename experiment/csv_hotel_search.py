"""
Deterministic hotel search against experiment/data/hotels.csv -- no model
involved, same split as csv_flight_search.py: code touches the real data
and does the arithmetic, the model only ever sees results, never the CSV.

Each city has exactly 3 hotels (cheap/mid/expensive). search_hotels_in_csv
always returns all 3, real, unfiltered -- so a caller doing cross-tool
budget math (flight + hotel) always has every tier's real price to work
with. If `max_budget` is given, it ALSO computes a single-component
verdict (best affordable tier, remaining budget, cost to the next tier)
for hotel-only requests -- same shape of answer as csv_flight_search.py's
"found" / "over_budget" split.
"""

from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent / "data" / "hotels.csv"

TIER_ORDER = ["cheap", "mid", "expensive"]


def _load(df: pd.DataFrame | None) -> pd.DataFrame:
    return df if df is not None else pd.read_csv(DATA_PATH)


def get_all_tiers(city: str, df: pd.DataFrame | None = None) -> list[dict]:
    """Real, unfiltered hotel rows for `city`, ordered cheap -> mid ->
    expensive. Empty list if the city isn't in the dataset at all."""
    df = _load(df)
    rows = df[df["City"] == city].to_dict("records")
    order = {tier: i for i, tier in enumerate(TIER_ORDER)}
    return sorted(rows, key=lambda r: order.get(r["Hotel_Tier"], 99))


def search_hotels_in_csv(city: str, max_budget: float | None = None, df: pd.DataFrame | None = None) -> dict:
    """Deterministic search. Always includes `all_tiers` (real, unfiltered).

    If `max_budget` is given, also includes a single-component verdict:
    - no city in the data at all: status "no_city"
    - nothing fits alone: status "over_budget", plus shortfall to the
      cheapest tier
    - one or more tiers fit: status "found", `best_tier` = the highest
      (priciest) tier that still fits, plus remaining_budget and
      amount_needed_for_next_tier (0 if already at the top tier)

    If `max_budget` is None, status is "tiers_only" -- real data with no
    verdict, since there's nothing honest to compare it against.
    """
    tiers = get_all_tiers(city, df=df)

    if not tiers:
        return {"status": "no_city", "city": city, "all_tiers": []}

    if max_budget is None:
        return {"status": "tiers_only", "city": city, "all_tiers": tiers}

    affordable = [t for t in tiers if t["Hotel_Price"] <= max_budget]

    if not affordable:
        cheapest = tiers[0]
        return {
            "status": "over_budget",
            "city": city,
            "budget": max_budget,
            "all_tiers": tiers,
            "cheapest_price": cheapest["Hotel_Price"],
            "shortfall": round(cheapest["Hotel_Price"] - max_budget, 2),
        }

    best = affordable[-1]  # affordable is already cheap->expensive order
    best_index = tiers.index(best)
    next_tier = tiers[best_index + 1] if best_index + 1 < len(tiers) else None

    return {
        "status": "found",
        "city": city,
        "budget": max_budget,
        "all_tiers": tiers,
        "best_tier": best,
        "remaining_budget": round(max_budget - best["Hotel_Price"], 2),
        "amount_needed_for_next_tier": round(next_tier["Hotel_Price"] - max_budget, 2) if next_tier else 0,
        "next_tier": next_tier,
    }
