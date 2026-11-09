"""agents/voice_summary.py -- uses FakeLLM, no network."""

from agents.voice_summary import build_voice_summary
from tests.fake_llm import FakeLLM, RecordingFakeLLM
from tests.test_app import _base_state


class _BrokenLLM:
    def invoke(self, prompt):
        raise RuntimeError("endpoint down")


def test_uses_llm_text_cleaned_for_speech():
    out = build_voice_summary(_base_state(), llm=FakeLLM("**Enjoy Paris!** See the Eiffel Tower."))
    assert out == "Enjoy Paris! See the Eiffel Tower."


def test_length_cap_is_enforced():
    long_text = "Paris is lovely and the Eiffel Tower is nearby. " * 40
    out = build_voice_summary(_base_state(), llm=FakeLLM(long_text), max_chars=200)
    assert len(out) <= 200


def test_prompt_contains_trip_facts_but_no_airport_codes():
    llm = RecordingFakeLLM("Enjoy Paris.")
    build_voice_summary(_base_state(), llm=llm)
    prompt = llm.prompts[0]
    assert "Eiffel Tower" in prompt and "Test Hotel" in prompt
    assert "JFK" not in prompt and "CDG" not in prompt


def test_falls_back_to_template_when_llm_names_an_invented_city():
    out = build_voice_summary(_base_state(), llm=FakeLLM("You could also take a day trip to Vancouver."))
    assert "Vancouver" not in out
    assert "Paris" in out


def test_falls_back_to_template_when_llm_fails():
    out = build_voice_summary(_base_state(), llm=_BrokenLLM())
    assert "6 day trip to Paris, France in April" in out
    assert "Test Hotel" in out and "Eiffel Tower" in out


def test_template_handles_missing_flight_and_hotel():
    state = _base_state(flight_results=[], hotel_results=[], spot_results=[])
    out = build_voice_summary(state, llm=_BrokenLLM())
    assert "Paris" in out and "budget" in out
