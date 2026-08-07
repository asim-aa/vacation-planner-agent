"""
classify_followup() tries keyword matching first (no LLM call at all) and
only falls back to a constrained LLM classification when no keyword
matches -- these tests verify both paths, and that the LLM fallback is
clamped to the valid category set.
"""

from agents.followup_router import classify_followup
from tests.fake_llm import FakeLLM, RecordingFakeLLM


def test_hotel_keyword_classified_without_calling_llm():
    llm = RecordingFakeLLM()
    assert classify_followup("spend the rest on a nicer hotel", llm=llm) == "hotel"
    assert llm.prompts == []


def test_flight_keyword_classified_without_calling_llm():
    llm = RecordingFakeLLM()
    assert classify_followup("can I get a more direct flight", llm=llm) == "flight"
    assert llm.prompts == []


def test_activities_keyword_classified_without_calling_llm():
    llm = RecordingFakeLLM()
    assert classify_followup("show me better activities", llm=llm) == "activities"
    assert llm.prompts == []


def test_falls_back_to_llm_when_no_keyword_matches():
    llm = RecordingFakeLLM("hotel")
    result = classify_followup("I want the deluxe option for where I sleep", llm=llm)
    assert result == "hotel"
    assert len(llm.prompts) == 1


def test_llm_fallback_response_outside_valid_set_is_unclear():
    llm = FakeLLM("sure, anything you want!")
    assert classify_followup("make this trip better somehow", llm=llm) == "unclear"
