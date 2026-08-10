hotel prompt:
Build a hotel-search experiment that works alongside the existing flight-search experiment.
Use the existing flights CSV as the source of truth for the list of supported cities/destinations.
Create a new hotels CSV with exactly 3 hotel records per city:

* 1 cheap hotel
* 1 mid-range hotel
* 1 expensive hotel

Each hotel record should include at minimum:

* city
* hotel_name
* hotel_tier
* hotel_price

Use consistent tier values such as:

* cheap
* mid
* expensive

The hotel prices should be intentionally spaced so the model can reason about affordability and upgrades between tiers.
The system should support three request types:

1. Flight only
2. Hotel only
3. Flight + hotel

Tool-calling behavior:

* If the user asks only for a flight, call only the flight search tool.
* If the user asks only for a hotel, call only the hotel search tool.
* If the user asks for both a flight and hotel, call both tools.
* Do not call an unnecessary tool.

For flight + hotel requests, treat the user's stated budget as the total combined budget unless they explicitly specify separate budgets.
Example user request:
"Find me a flight from BOS to San Diego with a hotel for $500."
Expected logic:

1. Parse the origin, destination, requested components, and total budget.
2. Call the flight search tool for BOS → San Diego.
3. Call the hotel search tool for San Diego.
4. Retrieve the available cheap, mid, and expensive hotel options.
5. Calculate:
combined_price = flight_price + hotel_price
6. Compare each hotel tier against the total budget.
7. Return the highest hotel tier that fits within the user's budget.

For every evaluated combination, the agent should be able to calculate:

* flight_price
* hotel_price
* hotel_tier
* combined_price
* remaining_budget
* amount_over_budget
* amount_needed_for_next_tier

Use the following formulas:
remaining_budget = budget - combined_price
amount_over_budget = max(0, combined_price - budget)
amount_needed_for_next_tier = max(0, next_tier_combined_price - budget)
Required behavior:
Flight + hotel fits budget
If one or more combinations fit:

* Return the highest hotel tier the user can afford.
* Show the flight.
* Show the selected hotel.
* Show the combined total.
* Show the remaining budget.
* Tell the user how much more money they would need to upgrade to the next hotel tier, if one exists.

Example:
"Your $500 budget covers the flight plus the cheap hotel for $462 total. You have $38 remaining. You would need $54 more to upgrade to the mid-range hotel."
Flight + hotel does not fit budget
If even the cheapest flight + cheap hotel exceeds the budget:

* Clearly state that no flight + hotel combination fits.
* Calculate exactly how much additional money is required for the cheapest valid combination.

Example:
"The cheapest flight + hotel combination is $548, which is $48 over your $500 budget."
Partial affordability
If the user requests both flight and hotel but the budget cannot cover both, check whether the budget can cover either component independently.
For example:

* If the flight alone fits, tell the user that the flight is affordable but the combined trip is not.
* If a hotel alone fits, tell the user that the hotel is affordable but the combined trip is not.
* If neither fits, state that clearly.

Do not silently switch a flight + hotel request into a flight-only or hotel-only booking. Partial affordability should be presented as an alternative, not treated as a successful completion of the original request.
Flight-only requests
For flight-only requests:

* Call only the flight search tool.
* Compare the returned flight price against the user's budget, if one was provided.
* State whether the flight fits the budget.
* If it does not fit, calculate exactly how much additional budget is required.

Hotel-only requests
For hotel-only requests:

* Call only the hotel search tool.
* Return the highest hotel tier that fits within the user's budget.
* If a hotel fits, show the remaining budget and the amount needed to upgrade to the next tier.
* If no hotel fits, calculate how much additional money is needed for the cheap hotel.

Response requirements
Responses should clearly distinguish between:

* successful full-budget match
* full request over budget
* partial affordability
* upgrade opportunity

The model should never claim that a combination fits unless:
flight_price + hotel_price <= budget
The main purpose of this experiment is to evaluate whether the model can:

* correctly identify which tools are required
* avoid unnecessary tool calls
* combine results from multiple tools
* perform accurate budget calculations
* select the best affordable hotel tier
* explain upgrade costs
* handle requests that are over budget
* recognize when only part of the requested trip is affordable
* clearly distinguish between full success and partial affordability

Generate the hotels CSV and any hotel-search logic necessary to support this evaluation.