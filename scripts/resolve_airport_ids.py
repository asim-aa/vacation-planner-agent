"""
One-time helper: resolves skyId/entityId for the 8 airports this project
supports, via Air Scraper's /v1/flights/searchAirport. Airport IDs are
stable, so this only needs to be rerun if RapidAPI ever changes them
(unlikely) -- the results are hardcoded into tools/flight_tool.py's
KNOWN_AIRPORTS dict.

Costs 8 API requests against the RapidAPI free tier (20/month) each time
it's run -- don't run this casually.

Usage:
    python scripts/resolve_airport_ids.py
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

AIRPORTS = ["JFK", "ORD", "SEA", "LAX", "SFO", "ATL", "DFW", "DEN"]
RAPIDAPI_HOST = "sky-scrapper.p.rapidapi.com"


def main() -> None:
    key = os.environ["RAPIDAPI_KEY"]
    result = {}

    for code in AIRPORTS:
        resp = requests.get(
            f"https://{RAPIDAPI_HOST}/api/v1/flights/searchAirport",
            params={"query": code, "locale": "en-US"},
            headers={"x-rapidapi-host": RAPIDAPI_HOST, "x-rapidapi-key": key},
            timeout=15,
        )
        data = resp.json()
        match = None
        for item in data.get("data", []):
            params = item.get("navigation", {}).get("relevantFlightParams", {})
            if params.get("skyId") == code and item["navigation"]["entityType"] == "AIRPORT":
                match = params
                break

        if match:
            result[code] = {"skyId": match["skyId"], "entityId": match["entityId"]}
            print(f"{code}: OK -> {match['skyId']} / {match['entityId']}")
        else:
            print(f"{code}: NO EXACT MATCH FOUND")
        time.sleep(1)

    print()
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
