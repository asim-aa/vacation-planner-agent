# Hotel + Trip Combinations (from `data/hotels.csv`)

Sits alongside `possible_flight_combinations.md`. Same principle, one more moving part: two real tools (`search_flights`, `search_hotels`) instead of one, and — when a request needs both — a deterministic combined-budget calculation the model is never allowed to do itself.

## Hotel data

Every city in `flights.csv` gets exactly 3 hotels: cheap, mid, expensive. Prices are hand-set (not random) so the spacing between tiers is deliberate and reproducible — see `generate_hotels_csv.py`.

| City | Cheap | Mid | Expensive |
|---|---|---|---|
| BOS (Boston) | Boston Budget Inn — $90 | Boston Plaza Hotel — $166 | Boston Grand Resort & Spa — $292 |
| DEN (Denver) | Denver Budget Inn — $85 | Denver Plaza Hotel — $157 | Denver Grand Resort & Spa — $276 |
| DFW (Dallas/Fort Worth) | Dallas Budget Inn — $80 | Dallas Plaza Hotel — $148 | Dallas Grand Resort & Spa — $260 |
| JFK (New York) | New York Budget Inn — $140 | New York Plaza Hotel — $259 | New York Grand Resort & Spa — $455 |
| LAX (Los Angeles) | Los Angeles Budget Inn — $130 | Los Angeles Plaza Hotel — $240 | Los Angeles Grand Resort & Spa — $422 |
| MCO (Orlando) | Orlando Budget Inn — $95 | Orlando Plaza Hotel — $176 | Orlando Grand Resort & Spa — $309 |
| MIA (Miami) | Miami Budget Inn — $120 | Miami Plaza Hotel — $222 | Miami Grand Resort & Spa — $390 |
| ORD (Chicago) | Chicago Budget Inn — $100 | Chicago Plaza Hotel — $185 | Chicago Grand Resort & Spa — $325 |
| PHX (Phoenix) | Phoenix Budget Inn — $75 | Phoenix Plaza Hotel — $139 | Phoenix Grand Resort & Spa — $244 |
| SFO (San Francisco) | San Francisco Budget Inn — $150 | San Francisco Plaza Hotel — $278 | San Francisco Grand Resort & Spa — $488 |

**Total: 30 hotels, 10 cities x 3 tiers.** For the flight side (routes, prices, airlines), see the table in `possible_flight_combinations.md` — `trip_tool_calling_agent.py` searches the exact same `flights.csv`.

## How the combined system works

`trip_tool_calling_agent.py` gives the model two real tools, `search_flights` and `search_hotels`, and lets it decide which one(s) a request needs. Same "don't trust the LLM with facts" split as the flight-only experiment, with one addition: when a request needs *both* tools, the model is never trusted to add flight_price + hotel_price itself. Code does it, for every tier, and hands the model a `VERIFIED budget analysis` block it's instructed to use verbatim.

```
remaining_budget            = budget - combined_price
amount_over_budget          = max(0, combined_price - budget)
amount_needed_for_next_tier = max(0, next_tier_combined_price - budget)
```

Because hotel tiers are strictly increasing in price, the set of affordable tiers is always a contiguous prefix (cheap, then cheap+mid, then all three) — so "the best tier you can afford" is always just the last one that still fits. That lets the code pick the right tier without any search logic, just a sort and a filter.

### A real finding: the model won't reliably call both tools in one turn

The first version of this agent did a single round: send the prompt, whatever tools the model calls in that one response are the tools that run, done. Tested live against `openai/gpt-oss-20b` (via Groq) with a combined request ("flight from BOS to MIA with a hotel for $500") — it called `search_flights` and then just... stopped. No `search_hotels` call, empty final answer. Repeated 3 times, same result every time.

Fix: `plan_trip_via_tool_calling` now loops — execute whatever tools the model asked for this round, feed the real results back, and ask again, up to `max_rounds=4`. In practice the model then calls the second tool on its own in round 2 once it sees the first tool's result and still has an unmet part of the request. The combined-budget analysis only gets computed and injected once *both* results exist, however many rounds that takes.

This is itself a piece of evaluation data, not just a bug fix: it means "correctly identify which tools are required" and "combine results from multiple tools" are not free just because you hand the model two `@tool`-decorated functions — a single-shot design would have silently under-served every combined request.

## Example commands (run from `vacation-planner-agent-experiment/`, venv already active)

All single-quoted so the shell doesn't swallow the `$` (see `possible_flight_combinations.md` for what happens when you don't).

### Flight only — calls only `search_flights`

```bash
python3 experiment/run_trip_experiment.py 'I need a flight from BOS to MIA, budget $200'
```
Tool calls: `search_flights` only. 3 real flights at $123.86, well under budget.

```bash
python3 experiment/run_trip_experiment.py 'I want a flight from DFW to MIA, budget $200'
```
Tool calls: `search_flights` only. Cheapest real flight is $330.41 — correctly reports over budget by $130.41, no hotel tool touched.

### Hotel only — calls only `search_hotels`

```bash
python3 experiment/run_trip_experiment.py 'Find me a hotel in LAX for $150'
```
Tool calls: `search_hotels` only. Best affordable tier: cheap ($130), $20 remaining, $90 more needed to reach mid ($240).

```bash
python3 experiment/run_trip_experiment.py 'I want a hotel in SFO, budget $50'
```
Tool calls: `search_hotels` only. Cheapest real hotel is $150 — correctly reports over budget by $100.

### Flight + hotel, fits budget

```bash
python3 experiment/run_trip_experiment.py 'Find me a flight from BOS to MIA with a hotel for $500'
```
Both tools called. Flight $123.86 + mid hotel $222 = $345.86, fits. Model reports $154.14 remaining and correctly says upgrading to the expensive tier ($390 hotel, $513.86 combined) would put you $13.86 over — so mid is the right call, matching `amount_needed_for_next_tier`.

### Flight + hotel, doesn't fit even at the cheapest tier

```bash
python3 experiment/run_trip_experiment.py 'Find me a flight from LAX to PHX with a hotel, total budget $40'
```
Both tools called. Cheapest flight $54.78 + cheapest hotel $75 = $129.78 combined, budget $40 — neither component fits alone either. Model states plainly that nothing here works, off by $89.78.

### Partial affordability — flight fits alone, hotel doesn't

```bash
python3 experiment/run_trip_experiment.py 'Find me a flight from LAX to PHX with a hotel, total budget $65'
```
Both tools called. Flight $54.78 fits under $65; cheapest hotel is $75, over budget; combined $129.78 is nowhere close. Model correctly separates the two: flight alone works, the full trip doesn't — not silently downgraded to a flight-only booking.

### Partial affordability — hotel fits alone, flight doesn't

```bash
python3 experiment/run_trip_experiment.py 'Find me a flight from DFW to MIA with a hotel, total budget $200'
```
Both tools called. Cheapest hotel $120 fits under $200; cheapest flight is $330.41, over budget on its own. `cheapest_hotel_alone_fits: True` in the verified analysis — worth checking the model's wording here specifically: in testing it correctly did the math but was less explicit than the flight-alone case about stating "the hotel alone is affordable," so this prompt is a good one to watch for phrasing quality, not just correctness.

### No budget stated on a combined request

```bash
python3 experiment/run_trip_experiment.py 'Find me a flight from BOS to MIA and a hotel there'
```
Both tools called (with `max_budget` omitted from both). No number is invented — the model lists the real flight and hotel options it found and asks you to state a budget before it will judge affordability.

### Broken (shell swallows the budget) — for comparison

```bash
python3 experiment/run_trip_experiment.py "Find me a flight from BOS to MIA with a hotel for $500"
```
Double-quoted, so `$500` is swallowed by the shell before Python ever sees it. Both tools still get called, but with `max_budget` omitted from each — same honest "ask instead of guess" behavior as the flight-only experiment, not a false match.
