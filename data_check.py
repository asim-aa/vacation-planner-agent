"""
Idempotent loader/verifier for the vacation-planner mock datasets.

Reads the raw Kaggle CSVs from data/raw/ into data/vacation.db (SQLite),
one table per dataset (hotels, flights, destinations). Safe to rerun: each
table is dropped and reloaded from the CSVs rather than appended to, so
reruns never duplicate rows.

Usage:
    python data_check.py
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "vacation.db"

HOTELS_CSV = RAW_DIR / "hotels.csv"
FLIGHTS_CSV = RAW_DIR / "synthetic_flight_passenger_data.csv"
DESTINATIONS_CSV = RAW_DIR / "Tourist_Destinations.csv"

HOTELS_CHUNKSIZE = 200_000

# The raw hotels dataset has no price field. Nightly rates are synthesized
# deterministically from HotelRating (banded) plus a small bump for facility
# richness, keyed off HotelCode so the same hotel always gets the same price
# across reruns. Replace this with a real pricing lookup in v2 without
# touching the Hotel Agent tool's query interface (it just reads the
# EstimatedPriceUSD column).
RATING_PRICE_BANDS = {
    "OneStar": (30, 60),
    "TwoStar": (50, 90),
    "ThreeStar": (80, 150),
    "FourStar": (140, 260),
    "FiveStar": (250, 500),
}
DEFAULT_PRICE_BAND = (60, 180)  # used for "All" / unrated hotels


def add_synthetic_price(df: pd.DataFrame) -> pd.DataFrame:
    lo = df["HotelRating"].map(lambda r: RATING_PRICE_BANDS.get(r, DEFAULT_PRICE_BAND)[0])
    hi = df["HotelRating"].map(lambda r: RATING_PRICE_BANDS.get(r, DEFAULT_PRICE_BAND)[1])
    span = (hi - lo + 1).astype(np.int64)

    hotel_code = pd.to_numeric(df["HotelCode"], errors="coerce").fillna(0).astype(np.int64)
    offset = hotel_code.abs() % span
    base_price = lo + offset

    facility_len = df["HotelFacilities"].fillna("").str.len()
    facility_bonus = (facility_len / 50).clip(upper=40)

    df["EstimatedPriceUSD"] = (base_price + facility_bonus).round(2)
    df["PriceSource"] = "synthetic_v1"
    return df

# Key columns from the ticket spec, mapped to the columns that actually
# exist in the raw CSVs. Where a spec column has no real match, the closest
# available substitute is used and flagged below.
EXPECTED_COLUMNS = {
    "hotels": {
        "cityName": "cityName",
        "hotel_name": "HotelName",  # spec used snake_case; real column is HotelName
        "HotelRating": "HotelRating",
        "HotelFacilities": "HotelFacilities",
        "price": "EstimatedPriceUSD",  # synthesized; raw dataset has no price field
    },
    "flights": {
        "airline": "Airline",
        "departure_airport": "Departure_Airport",
        "arrival_airport": "Arrival_Airport",
        "pricing": "Price_USD",
    },
    "destinations": {
        # None of these three spec names exist verbatim in the raw CSV.
        # Closest real columns are substituted and called out in the summary.
        "Destination Category": "Type",
        "Estimated Daily Cost": "Avg Cost (USD/day)",
        "Seasonal Suitability": "Best Season",
    },
}


def load_hotels(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS hotels")
    first = True
    for chunk in pd.read_csv(
        HOTELS_CSV, chunksize=HOTELS_CHUNKSIZE, skipinitialspace=True, encoding="latin1"
    ):
        chunk.columns = [c.strip() for c in chunk.columns]
        chunk = add_synthetic_price(chunk)
        chunk.to_sql("hotels", conn, if_exists="replace" if first else "append", index=False)
        first = False

    # hotels has ~1M rows; every search_hotels() call filters on
    # LOWER(cityName), which needs an expression index to avoid a full
    # table scan (a plain index on cityName wouldn't be used here).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hotels_city_lower ON hotels (LOWER(cityName))")


def load_flights(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS flights")
    df = pd.read_csv(FLIGHTS_CSV, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df.to_sql("flights", conn, if_exists="replace", index=False)


def load_destinations(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS destinations")
    df = pd.read_csv(DESTINATIONS_CSV, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df.to_sql("destinations", conn, if_exists="replace", index=False)


def verify_table(conn: sqlite3.Connection, table: str) -> None:
    print(f"\n=== {table} ===")
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"row count: {row_count}")

    actual_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for spec_col, real_col in EXPECTED_COLUMNS[table].items():
        status = "OK" if real_col in actual_columns else "MISSING"
        marker = "" if spec_col == real_col else f"  (spec called it '{spec_col}')"
        print(f"  [{status}] {real_col}{marker}")

    sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
    print(sample.to_string())


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        load_hotels(conn)
        load_flights(conn)
        load_destinations(conn)
        conn.commit()

        for table in ("hotels", "flights", "destinations"):
            verify_table(conn, table)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
