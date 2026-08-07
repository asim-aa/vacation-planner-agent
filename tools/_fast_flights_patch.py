"""
Monkeypatch for a real bug in fast-flights 3.0.2 (latest as of writing):
fast_flights.parser.parse_js() crashes the ENTIRE parse with an unhandled
IndexError/TypeError the moment a single itinerary in Google's response
has no price attached (its price array is empty) -- e.g. a "track price"
or currently-unbookable-by-Google itinerary mixed in among priced ones.

Verified in practice: LAX->CGK and BOI->CGK both returned zero flights
via our own code, but the *raw* fast_flights.get_flights() call for the
same routes threw IndexError ("k[1][0][1]") / TypeError ("payload[3][0]"
adjacent access) instead of returning results -- meaning real, priced
flights in the response were being discarded wholesale because of one
unrelated bad record. This mirrors a bug class we already guard against
in our own search_flights() (one malformed record shouldn't kill the
whole batch); the fix has to live here too since it's inside the
third-party parser, upstream of anything our own code sees.

Two distinct upstream bugs are fixed here:
1. One malformed itinerary record (no price attached) crashes the parse
   of every OTHER record in the same response -- fixed with a per-record
   try/except, same pattern as our own search_flights().
2. Upstream only guards `payload[3][0] is None` (a legitimate "no
   results" shape) but not `payload[3] is None` (also a legitimate
   "no results" shape, seen live on BOI->CGK) -- the latter crashes with
   an unhandled TypeError instead of returning an empty result list.

Importing this module applies the patch as a side effect. It is a
drop-in copy of fast_flights.parser.parse_js with the per-record body
wrapped in try/except so one bad record is skipped instead of wiping out
every result.
"""

import json

import fast_flights.parser as _ff_parser
from fast_flights.exceptions import FlightsNotFound
from fast_flights.model import (
    Airline,
    Airport,
    Alliance,
    CarbonEmission,
    Flights,
    JsMetadata,
    SimpleDatetime,
    SingleFlight,
)


def _patched_parse_js(js: str):
    data = js.split("data:", 1)[1].rsplit(",", 1)[0]

    if data.endswith("errorHasStatus: true"):
        raise FlightsNotFound("no flights found; received error")

    payload = json.loads(data)

    alliances = []
    airlines = []

    (alliances_data, airlines_data) = (
        payload[7][1][0],
        payload[7][1][1],
    )

    for code, name in alliances_data:
        alliances.append(Alliance(code=code, name=name))

    for code, name in airlines_data:
        airlines.append(Airline(code=code, name=name))

    meta = JsMetadata(alliances=alliances, airlines=airlines)

    flights = _ff_parser.ResultList()
    if payload[3] is None or payload[3][0] is None:
        flights.metadata = meta
        return flights

    for k in payload[3][0]:
        try:
            flight = k[0]
            price = k[1][0][1]  # empty for some price-less/tracked itineraries

            typ = flight[0]
            flight_airlines = flight[1]

            sg_flights = []
            for single_flight in flight[2]:
                from_airport = Airport(code=single_flight[3], name=single_flight[4])
                to_airport = Airport(code=single_flight[6], name=single_flight[5])
                departure = SimpleDatetime(date=single_flight[20], time=single_flight[8])
                arrival = SimpleDatetime(date=single_flight[21], time=single_flight[10])
                sg_flights.append(
                    SingleFlight(
                        from_airport=from_airport,
                        to_airport=to_airport,
                        departure=departure,
                        arrival=arrival,
                        duration=single_flight[11],
                        plane_type=single_flight[17],
                    )
                )

            extras = flight[22]
            flights.append(
                Flights(
                    type=typ,
                    price=price,
                    airlines=flight_airlines,
                    flights=sg_flights,
                    carbon=CarbonEmission(typical_on_route=extras[8], emission=extras[7]),
                )
            )
        except (IndexError, TypeError, KeyError):
            continue

    flights.metadata = meta
    return flights


_ff_parser.parse_js = _patched_parse_js
