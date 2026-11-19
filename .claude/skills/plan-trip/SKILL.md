---
name: plan-trip
description: Plan a vacation from one sentence (destination, budget, duration, month) using this repo's multi-agent LangGraph pipeline, then verify the itinerary's math and honesty before presenting it. Use when the user asks to plan, price, or refine a trip.
---

# plan-trip

Turns a one-line trip request into a verified itinerary with an itemized budget.
Wraps the pipeline in `agents/graph.py` (flights, hotels, spots+weather in
parallel -> budget -> compiler) and adds a deterministic verification gate so
the answer you give is never an unchecked LLM claim.

## Inputs
A natural-language request. If any of these are missing, ask once, then proceed
with stated defaults (origin defaults to New York; the pipeline does this too):
destination, total budget (USD), duration (days), travel month.

## Steps
1. **Run the pipeline** from the repo root:
   `python .claude/skills/plan-trip/scripts/run_plan.py "<request>" > /tmp/trip.json`
   Needs `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` (see `.env.example`).
   Flight/hotel/place/weather data is live and keyless.
2. **Verify** the result:
   `python .claude/skills/plan-trip/scripts/verify_itinerary.py /tmp/trip.json`
   Exit code 0 = pass. Non-zero prints each failed check. Do not present an
   itinerary that fails; report the failure and what you'd retry.
3. **Present** `itinerary_markdown`, then add a short "Caveats" section:
   - Activity costs are a coarse OSM fee-tag heuristic, not real prices.
   - "Well-known" means "has a Wikipedia/Wikidata entry", not popularity.
   - Self-connected (two-ticket) flights carry missed-connection risk.
   - Flight/hotel prices are live scrapes and change.
4. **Refine** (user says "nicer hotel", "more direct flight", ...): use the
   keyword routing in `agents/followup_router.py`; re-rank already-fetched
   results rather than re-scraping.

## What the verifier checks (scripts/verify_itinerary.py)
- Total equals flights + lodging + activities (to the cent).
- Budget status line agrees with total vs budget (no "within budget" when over).
- Every day 1..N appears exactly once in the chronological itinerary.
- Required sections present; no empty/"No ... data" sections silently shipped
  (reported as warnings so the user hears about gaps).

## Failure handling
- Zero flights/hotels: say so plainly; never fabricate a substitute.
- Over budget: show by how much and offer the cheapest lever (hotel ceiling,
  month shift) rather than hiding it.
