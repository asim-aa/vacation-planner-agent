"""
Flight Agent tool: queries the local flights table
(synthetic-airline-passenger-and-flight-data, loaded into SQLite by
data_check.py) for ticket options and baseline pricing on a route.

Note: the raw dataset only covers 8 US domestic airports (JFK, ORD, SEA,
LAX, SFO, ATL, DFW, DEN) -- there is no international route coverage.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "vacation.db"


def search_flights(
    origin: str,
    destination: str,
    seat_class: str | None = None,
    max_price: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return flight ticket rows for `origin` -> `destination` (exact airport
    code match, case-insensitive), optionally filtered by seat class and/or
    capped at `max_price`, cheapest first.

    Returns an empty list if no flights match.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT Airline, Departure_Airport, Arrival_Airport, Seat_Class, Price_USD
            FROM flights
            WHERE UPPER(Departure_Airport) = UPPER(?) AND UPPER(Arrival_Airport) = UPPER(?)
        """
        params: list = [origin.strip(), destination.strip()]

        if seat_class is not None:
            query += " AND Seat_Class = ?"
            params.append(seat_class)

        if max_price is not None:
            query += " AND Price_USD <= ?"
            params.append(max_price)

        query += " ORDER BY Price_USD ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_baseline_price(
    origin: str,
    destination: str,
    seat_class: str = "Economy",
) -> float | None:
    """Return the average ticket price for `origin` -> `destination` in the
    given seat class, for use as a baseline flight cost in budget math.

    Returns None if no matching flights exist for that route/class.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """
            SELECT AVG(Price_USD)
            FROM flights
            WHERE UPPER(Departure_Airport) = UPPER(?)
              AND UPPER(Arrival_Airport) = UPPER(?)
              AND Seat_Class = ?
            """,
            (origin.strip(), destination.strip(), seat_class),
        ).fetchone()
        return round(row[0], 2) if row and row[0] is not None else None
    finally:
        conn.close()


if __name__ == "__main__":
    print("Baseline economy JFK->ATL:", get_baseline_price("JFK", "ATL"))
    for flight in search_flights("JFK", "ATL", seat_class="Economy", limit=5):
        print(flight)
    print("No-match test:", search_flights("XXX", "YYY"))
