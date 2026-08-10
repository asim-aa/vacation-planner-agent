"""
Second experiment variant: real tool/function calling, instead of the
manual "extract JSON, then code searches" split in csv_flight_search.py.

Architecture requested: the model gets ONLY the user prompt and a tool
definition (search_flights) -- it does NOT get the CSV, and it does NOT
get a hand-written extraction schema in the prompt text. The model
decides on its own whether/how to call the tool; the tool's owner (this
module, playing "the agent that owns the function") actually executes
it against the real CSV and hands the result back to the model, which
then writes the final natural-language answer from real data.

This is two model calls, not one:
    call 1: user prompt -> model decides to call search_flights(...)
    (we execute the tool for real, against the CSV)
    call 2: tool result -> model -> final natural-language answer

That's a real cost (more calls than the deterministic version), not a
speed win -- the benefit is the model composing a real answer from real
results instead of code printing a template.

Same defensive lesson as csv_flight_search.py carries over: max_budget
is OPTIONAL in the tool schema on purpose. If it were required, the
model would feel pressured to invent a number when the user didn't
state one -- exactly the bug that motivated removing the $500 default
there. Here, an omitted budget is handled explicitly, not guessed.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agents.llm_client import get_llm
from experiment.csv_flight_search import AIRPORT_NAMES, search_flights_in_csv

_AIRPORT_LIST_TEXT = ", ".join(f"{code} ({name})" for code, name in AIRPORT_NAMES.items())

SYSTEM_PROMPT = f"""You are a flight-search assistant. You have one tool,
search_flights, backed by a real dataset of actual flights -- you cannot
answer flight questions from your own knowledge, you must call the tool.

The dataset only covers these airports: {_AIRPORT_LIST_TEXT}.

If the user did not state a budget, do NOT invent one -- call the tool
with max_budget omitted (or null), and it will tell you to ask the user
for a real number instead of guessing.

After the tool returns real results, write a short, direct answer using
ONLY what the tool actually returned -- do not add flights, prices, or
airlines the tool didn't give you."""


@tool
def search_flights(origin_airport: str, destination_airport: str, max_budget: float | None = None) -> dict:
    """Search real flight data for non-cancelled flights between two airports within a budget.

    Args:
        origin_airport: 3-letter IATA code the user is flying FROM.
        destination_airport: 3-letter IATA code the user wants to fly TO.
        max_budget: maximum total price in USD. Omit this entirely if the
            user did not state a budget -- do not guess one.
    """
    origin = origin_airport.strip().upper()
    destination = destination_airport.strip().upper()

    if max_budget is None:
        return {
            "status": "no_budget_stated",
            "origin": origin,
            "destination": destination,
            "note": "The user did not state a budget. Ask them for one instead of assuming a number.",
        }

    return search_flights_in_csv(origin, destination, float(max_budget))


def plan_flight_via_tool_calling(user_request: str, llm=None) -> dict:
    """The full two-call agentic flow. Returns both calls' raw output so a
    caller (or a test) can inspect exactly what happened at each step."""
    llm = llm or get_llm()
    bound_llm = llm.bind_tools([search_flights])

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_request)]

    # Call 1: model sees ONLY the prompt + the tool's schema -- never the CSV.
    first_response: AIMessage = bound_llm.invoke(messages)
    messages.append(first_response)

    if not first_response.tool_calls:
        # Model answered without calling the tool at all -- treat that as
        # not having real data behind it, same "don't trust untethered
        # LLM output" stance as the rest of this project.
        return {
            "tool_call": None,
            "tool_result": None,
            "final_answer": first_response.content,
            "note": "Model did not call the tool -- this answer is NOT backed by real data.",
        }

    tool_call = first_response.tool_calls[0]

    # This is "the agent that owns the function" actually running it --
    # against the real CSV, not the model's imagination.
    tool_result = search_flights.invoke(tool_call["args"])
    messages.append(ToolMessage(content=json.dumps(tool_result, default=str), tool_call_id=tool_call["id"]))

    # Call 2: model reads the REAL tool result and writes the final answer.
    second_response: AIMessage = bound_llm.invoke(messages)

    return {
        "tool_call": tool_call,
        "tool_result": tool_result,
        "final_answer": second_response.content,
    }
