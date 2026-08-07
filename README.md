# Vacation Planner Agent

A multi-agent vacation planner built with [LangGraph](https://github.com/langchain-ai/langgraph). Give it one sentence — destination, budget, duration, and travel month — and independent Flight, Hotel, and Spots & Weather agents research it in parallel, then a budget step and a final compiler assemble one itinerary with an itemized cost breakdown.

Every data source is live and free. **No API keys required anywhere in the system.**

![Tests](https://github.com/asim-aa/vacation-planner-agent/actions/workflows/tests.yml/badge.svg)

*Demo video coming soon.*

## From mock data to live data

This was built in two deliberate phases. **v1** proved the multi-agent architecture end-to-end against local mock datasets (Kaggle CSVs loaded into SQLite) — so the LangGraph orchestration, parallel fan-out/fan-in, budget math, and itinerary compilation could be validated in isolation before taking on the complexity of real, uncontrolled APIs. Once that pipeline worked with a full test suite behind it, **v2** replaced every single mock data source with something live, one at a time: flights (started on a rate-limited RapidAPI plan, then rebuilt on the keyless `fast-flights` after hitting its quota), hotels (`fast-hotels`), destinations (OpenStreetMap), and climate (Open-Meteo) — landing on zero API keys required anywhere in the final system.

## What it does

- **Flights** — live Google Flights results via [`fast-flights`](https://github.com/AWeirdDev/flights). Airport resolution is fully offline (`airportsdata`) and handles ambiguous multi-airport metros (e.g. Jakarta's CGK vs HLP) by trying ranked candidates instead of guessing once. When Google's own engine can't build any itinerary at all for a route (e.g. a small regional origin to a distant city), it falls back to self-assembling a connection through a major hub and clearly labels it as a two-ticket, self-connected itinerary rather than presenting it as a normal booking.
- **Hotels** — live Google Hotels results via `fast-hotels`, filtered to a per-night ceiling computed from whatever budget is left after flights and activities.
- **Activities** — real, named tourist attractions from OpenStreetMap (Nominatim geocoding + Overpass POI queries), ranked by season fit and distance from the city center. Places with a real Wikipedia/Wikidata entry are flagged as "well-known" — OSM has no popularity data, so this is a real (if imperfect) proxy rather than a fabricated score.
- **Weather / season fit** — real historical climate data from Open-Meteo, checked at the destination's actual coordinates for the travel month.
- **Chat-based refinement** — after the itinerary is generated, ask for changes in plain English: *"spend the rest on a nicer hotel"*, *"get me a more direct flight"*, *"show me more well-known activities"*. A keyword-first classifier (falling back to a constrained single-word LLM call only when no keyword matches) routes the request to the right agent, which re-prioritizes among results already fetched — no redundant re-scraping, and an honest "that's already the best option" reply when nothing better exists.

## Architecture

```
parse_request
    -> [flight_agent, spots_weather_agent]   (parallel)
    -> compute_hotel_budget                   (turns remaining budget into a per-night ceiling)
    -> hotel_agent
    -> compile_itinerary
```

Built as a LangGraph `StateGraph`. Each sub-agent is a thin LangGraph node wrapping a plain-Python tool function — the LLM only ever sees a tool's already-parsed output, never raw scraped HTML or API responses. Every agent and tool is independently unit-testable via dependency injection (`llm=None` defaults to the real client; tests inject a fake).

## Engineering notes

A few things worth calling out from building this against live, uncontrolled data rather than a fixture:

- **Found and patched a real bug in a third-party library.** `fast-flights` 3.0.2 crashes and silently discards an entire response when a single itinerary has no price attached, or when Google's "no results" payload takes a shape the library doesn't guard against. Patched via a monkeypatch (`tools/_fast_flights_patch.py`) with regression tests reproducing both crash shapes — verified live, this recovered real bookable flights that were previously being thrown away.
- **No silent failures.** Every live call (flight search, hotel search, geocoding, Overpass, weather) degrades to an empty result and a clear message instead of crashing the whole pipeline, with dedicated zero-result tests for every agent.
- **Honest about data limitations, in the UI itself.** OpenStreetMap has no star ratings, real per-visit pricing, or popularity data — activity costs are a coarse fee-tag heuristic and "well-known" means "has a Wikipedia/Wikidata entry." Both are stated explicitly rather than presented as real numbers.
- **Re-prioritize, don't re-search.** The chat refinement feature deliberately re-ranks results already fetched this run instead of hitting Google again — cheaper, faster, and avoids a live re-scrape silently returning a different result set than what's on screen.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then point `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` in `.env` at any OpenAI-compatible endpoint (a local model server, or a hosted provider). Nothing else in the app needs a key.

## Run it

```bash
streamlit run app.py
```

Or from the command line, for one itinerary at a time:

```bash
python demo_orchestrator.py "Plan me a 6 day trip to Tokyo in October, budget $3000, flying from Chicago"
```

## Tests

```bash
pytest                                       # 69 tests, fully offline (network calls mocked/gated)
RUN_LIVE_FLIGHT_TESTS=1 pytest tests/test_flight_tool.py -v    # opt-in live network tests, per tool
RUN_LIVE_HOTEL_TESTS=1 pytest tests/test_hotel_tool.py -v
RUN_LIVE_PLACES_TESTS=1 pytest tests/test_spots_weather_tool.py -v
```

CI runs the offline suite on every push via GitHub Actions.
