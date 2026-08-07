"""
Defensive guard against LLM narrative hallucinations that name a real
place outside the trip's actual scope -- e.g. a flight recommendation
that said "reaching Vancouver from San Jose" for a trip whose real
destination was Guangzhou. Nothing in the data given to the LLM
mentioned Vancouver; it was invented.

This pins facts in free text the same way this project already pins
numeric facts (price, stops, rating) by reading them straight from the
tool's output instead of trusting the LLM to restate them correctly.

Deliberately narrow and trigger-happy, not a general hallucination
detector: a false positive just means falling back to a plain templated
sentence (safe), while a false negative means trusting an invented place
name in a customer-facing recommendation (not safe). Callers must build
an `allowed_names` set that includes every real proper noun legitimately
part of THIS specific recommendation -- e.g. airline name, hotel name,
spot names -- since those can coincidentally collide with real city names
(verified: "Delta" is both a major US airline and a real town with its
own airport).
"""

import re

import airportsdata

_AIRPORTS = airportsdata.load("IATA")
_KNOWN_CITIES_LOWER = {a["city"].strip().lower() for a in _AIRPORTS.values() if a.get("city")}

# Greedily matches runs of capitalized words (candidate proper nouns),
# e.g. "New York" or "Vancouver" -- checked both as a whole phrase and
# word-by-word so multi-word runs (like "Newark Liberty International
# Airport") don't hide a single-word city inside them.
_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b")


def city_for_airport_code(code: str | None) -> str | None:
    """Offline reverse lookup: IATA code -> real city name, or None."""
    if not code:
        return None
    airport = _AIRPORTS.get(code)
    return airport["city"].strip() if airport else None


def _candidate_tokens(text: str) -> set[str]:
    tokens = set()
    for phrase in _PROPER_NOUN_RE.findall(text):
        tokens.add(phrase)
        tokens.update(phrase.split())
    return tokens


def mentions_unexpected_city(text: str, allowed_names: set) -> bool:
    """True if `text` names a real city (per airportsdata) that isn't in
    `allowed_names` -- a signal the LLM likely invented a place name.

    Allowed names are matched both as whole phrases and word-by-word
    (same tokenization as the candidates), so an allowed multi-word name
    like "New York" also covers its component word "York" -- otherwise
    that split would falsely flag "York" as a DIFFERENT, unexpected city
    (it really is one, on its own) even though it's just part of an
    allowed phrase here.
    """
    allowed_lower = set()
    for name in allowed_names:
        if not name:
            continue
        name = str(name).strip()
        allowed_lower.add(name.lower())
        allowed_lower.update(word.lower() for word in name.split())

    for token in _candidate_tokens(text):
        token_lower = token.lower()
        if token_lower in allowed_lower:
            continue
        if token_lower in _KNOWN_CITIES_LOWER:
            return True
    return False
