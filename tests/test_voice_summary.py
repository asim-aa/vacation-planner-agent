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


# --- Prompt content and who-wrote-it source ------------------------------

from agents.voice_summary import (  # noqa: E402
    SOURCE_AI,
    SOURCE_TEMPLATE_REJECTED,
    SOURCE_TEMPLATE_UNAVAILABLE,
    build_voice_summary_with_source,
)


def test_prompt_asks_for_second_person_future_tense_and_no_embellishment():
    llm = RecordingFakeLLM("You'll enjoy Paris.")
    build_voice_summary(_base_state(), llm=llm)
    prompt = llm.prompts[0]
    assert "UPCOMING" in prompt and "second person" in prompt
    assert "never write in the first person or the past tense" in prompt
    assert "opinions" in prompt and "closing remarks" in prompt


def test_prompt_includes_precomputed_round_trip_flight_total():
    llm = RecordingFakeLLM("You'll fly Delta.")
    build_voice_summary(_base_state(flight_cost_estimate=730.0), llm=llm)
    assert "'flight_total_round_trip': 730" in llm.prompts[0]
    assert "Do not do arithmetic" in llm.prompts[0]


def test_flight_total_falls_back_to_twice_the_one_way_price():
    llm = RecordingFakeLLM("You'll fly Delta.")
    state = _base_state()
    state.pop("flight_cost_estimate")
    build_voice_summary(state, llm=llm)
    assert "'flight_total_round_trip': 600" in llm.prompts[0]  # 2 x $300 one-way


def test_source_is_ai_when_the_llm_text_is_used():
    text, source = build_voice_summary_with_source(_base_state(), llm=FakeLLM("You'll visit the Eiffel Tower."))
    assert source == SOURCE_AI
    assert text == "You'll visit the Eiffel Tower."


def test_source_reports_llm_unavailable_on_failure_or_empty_text():
    assert build_voice_summary_with_source(_base_state(), llm=_BrokenLLM())[1] == SOURCE_TEMPLATE_UNAVAILABLE
    assert build_voice_summary_with_source(_base_state(), llm=FakeLLM("   "))[1] == SOURCE_TEMPLATE_UNAVAILABLE


def test_source_reports_guard_rejection_when_llm_names_an_invented_city():
    _, source = build_voice_summary_with_source(_base_state(), llm=FakeLLM("Then fly on to Vancouver."))
    assert source == SOURCE_TEMPLATE_REJECTED
