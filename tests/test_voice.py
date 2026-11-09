"""tools/voice.py -- every ElevenLabs HTTP call is mocked; CI never needs a
real key or network."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from tools import voice


def _resp(status=200, content=b"MP3DATA", json_data=None):
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.json.return_value = json_data
    return r


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    for name in ("ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL_ID", "VOICE_MAX_CHARS", "VOICE_MAX_PER_SESSION"):
        monkeypatch.delenv(name, raising=False)
    voice._synthesize_cached.cache_clear()
    voice.api_call_count = 0


def test_synthesize_returns_audio_bytes_and_sends_expected_request():
    with patch("tools.voice.requests.post", return_value=_resp()) as post:
        assert voice.synthesize("Hello there.") == b"MP3DATA"
    url = post.call_args.args[0]
    assert url.endswith(f"/v1/text-to-speech/{voice.DEFAULT_VOICE_ID}")
    assert post.call_args.kwargs["headers"]["xi-api-key"] == "test-key"
    assert post.call_args.kwargs["json"] == {"text": "Hello there.", "model_id": voice.DEFAULT_MODEL_ID}


def test_missing_key_raises_without_calling_api(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    with patch("tools.voice.requests.post") as post:
        with pytest.raises(voice.MissingKeyError):
            voice.synthesize("Hello")
    post.assert_not_called()


def test_empty_text_raises_without_calling_api():
    with patch("tools.voice.requests.post") as post:
        with pytest.raises(voice.VoiceError):
            voice.synthesize("   ")
    post.assert_not_called()


@pytest.mark.parametrize("status,fragment", [(401, "key"), (429, "rate"), (402, "quota"), (500, "500")])
def test_api_errors_become_friendly_voice_errors(status, fragment):
    with patch("tools.voice.requests.post", return_value=_resp(status=status)):
        with pytest.raises(voice.VoiceError, match=fragment):
            voice.synthesize("Hello")


def test_network_error_becomes_friendly_voice_error_and_never_leaks_key():
    with patch("tools.voice.requests.post", side_effect=requests.ConnectionError("boom test-key")):
        with pytest.raises(voice.VoiceError) as exc:
            voice.synthesize("Hello")
    assert "test-key" not in str(exc.value)


def test_cache_hit_avoids_a_second_api_call():
    with patch("tools.voice.requests.post", return_value=_resp()) as post:
        voice.synthesize_cached("Same text.")
        voice.synthesize_cached("Same text.")
    assert post.call_count == 1
    assert voice.api_call_count == 1


def test_cache_key_includes_voice_and_model(monkeypatch):
    with patch("tools.voice.requests.post", return_value=_resp()) as post:
        voice.synthesize_cached("Same text.")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "other-voice")
        voice.synthesize_cached("Same text.")
    assert post.call_count == 2


def test_errors_are_not_cached():
    with patch("tools.voice.requests.post", side_effect=[_resp(status=429), _resp()]) as post:
        with pytest.raises(voice.VoiceError):
            voice.synthesize_cached("Retry me.")
        assert voice.synthesize_cached("Retry me.") == b"MP3DATA"
    assert post.call_count == 2


def test_clean_for_speech_strips_markdown_and_whitespace():
    assert voice.clean_for_speech("# Title\n\n**Bold** and `code` | cell") == "Title Bold and code cell"


def test_clean_for_speech_enforces_cap_at_sentence_boundary():
    text = "First sentence is here. " * 10
    out = voice.clean_for_speech(text, max_chars=60)
    assert len(out) <= 60
    assert out.endswith(".")


def test_clean_for_speech_hard_cuts_when_no_sentence_boundary():
    assert len(voice.clean_for_speech("a" * 500, max_chars=100)) == 100


def test_session_limit_and_max_chars_defaults_and_overrides(monkeypatch):
    assert voice.get_session_limit() == 3
    assert voice.get_max_chars() == 800
    monkeypatch.setenv("VOICE_MAX_PER_SESSION", "5")
    monkeypatch.setenv("VOICE_MAX_CHARS", "500")
    assert (voice.get_session_limit(), voice.get_max_chars()) == (5, 500)


def test_fetch_quota_parses_subscription():
    data = {"character_count": 1200, "character_limit": 10000}
    with patch("tools.voice.requests.get", return_value=_resp(json_data=data)):
        assert voice.fetch_quota() == {"used": 1200, "limit": 10000}


def test_fetch_quota_returns_none_when_key_lacks_permission():
    with patch("tools.voice.requests.get", return_value=_resp(status=401)):
        assert voice.fetch_quota() is None


def test_fetch_quota_returns_none_on_network_error():
    with patch("tools.voice.requests.get", side_effect=requests.Timeout()):
        assert voice.fetch_quota() is None


# --- Global monthly cap ---------------------------------------------------

def test_global_cap_default_and_override(monkeypatch):
    assert voice.get_global_cap() == 8000
    monkeypatch.setenv("VOICE_GLOBAL_CHAR_CAP", "123")
    assert voice.get_global_cap() == 123


def test_real_calls_are_counted_toward_the_global_cap():
    with patch("tools.voice.requests.post", return_value=_resp()):
        voice.synthesize_cached("x" * 100)
        voice.synthesize_cached("y" * 50)
    assert voice.global_chars_used() == 150


def test_cache_hits_do_not_count_toward_the_global_cap():
    with patch("tools.voice.requests.post", return_value=_resp()):
        voice.synthesize_cached("x" * 100)
        voice.synthesize_cached("x" * 100)
    assert voice.global_chars_used() == 100


def test_cap_blocks_api_call_when_it_would_be_exceeded(monkeypatch):
    monkeypatch.setenv("VOICE_GLOBAL_CHAR_CAP", "150")
    with patch("tools.voice.requests.post", return_value=_resp()) as post:
        voice.synthesize_cached("x" * 100)
        with pytest.raises(voice.CapReachedError, match="monthly"):
            voice.synthesize_cached("y" * 60)
    assert post.call_count == 1
    assert voice.global_chars_used() == 100


def test_cached_audio_is_still_served_after_cap_is_reached(monkeypatch):
    monkeypatch.setenv("VOICE_GLOBAL_CHAR_CAP", "100")
    with patch("tools.voice.requests.post", return_value=_resp()):
        voice.synthesize_cached("x" * 100)
        assert voice.synthesize_cached("x" * 100) == b"MP3DATA"


def test_failed_api_calls_do_not_use_up_the_cap():
    with patch("tools.voice.requests.post", return_value=_resp(status=429)):
        with pytest.raises(voice.VoiceError):
            voice.synthesize_cached("x" * 100)
    assert voice.global_chars_used() == 0


def test_usage_resets_in_a_new_month(monkeypatch):
    with patch("tools.voice.requests.post", return_value=_resp()):
        voice.synthesize_cached("x" * 100)
    monkeypatch.setattr(voice, "_current_month", lambda: "2099-01")
    assert voice.global_chars_used() == 0


def test_corrupt_usage_file_is_treated_as_zero(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("not json{")
    monkeypatch.setenv("VOICE_USAGE_FILE", str(bad))
    assert voice.global_chars_used() == 0
