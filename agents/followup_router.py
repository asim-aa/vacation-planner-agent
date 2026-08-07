"""
Classifies a free-text trip-refinement follow-up (e.g. "spend the rest
on a nicer hotel") into which sub-agent it targets, so the chat UI in
app.py knows which refine_* function to call.

Keyword matching first -- cheap and fully reliable for the phrasings
people actually type -- falls back to a tightly constrained single-word
LLM classification only when no keyword matches. This project has
already hit real LLM-parsing reliability issues on more open-ended
extraction (see agents/parse_request.py's history), so the keyword path
is deliberately the primary mechanism, not the LLM.
"""

from agents.llm_client import get_llm

HOTEL_KEYWORDS = ["hotel", "stay", "room", "lodging", "accommodation"]
FLIGHT_KEYWORDS = ["flight", "fly", "plane", "airline", "airport", "layover", "connection"]
ACTIVITY_KEYWORDS = ["activit", "spot", "attraction", "museum", "sightsee", "tour", "landmark"]

VALID_CATEGORIES = {"hotel", "flight", "activities"}


def classify_followup(text: str, llm=None) -> str:
    """Returns "hotel", "flight", "activities", or "unclear"."""
    lowered = text.lower()
    if any(k in lowered for k in HOTEL_KEYWORDS):
        return "hotel"
    if any(k in lowered for k in FLIGHT_KEYWORDS):
        return "flight"
    if any(k in lowered for k in ACTIVITY_KEYWORDS):
        return "activities"

    llm = llm or get_llm()
    prompt = (
        "Classify this vacation-planning follow-up request into EXACTLY "
        "one word: hotel, flight, activities, or unclear. Only output "
        f"that one word, nothing else.\n\nRequest: {text}"
    )
    label = llm.invoke(prompt).content.strip().lower()
    return label if label in VALID_CATEGORIES else "unclear"
