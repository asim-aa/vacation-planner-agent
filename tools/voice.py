"""
Thin ElevenLabs text-to-speech client.

Deliberately plain `requests` against one endpoint
(POST /v1/text-to-speech/{voice_id}) instead of the `elevenlabs` SDK: it's
one call, `requests` is already a dependency, and a single `requests.post`
is trivial to mock in CI. No Streamlit imports here, so it's unit-testable.

The API key is read from the ELEVENLABS_API_KEY environment variable (the
Streamlit layer copies it in from st.secrets). It is never logged or put
in an exception message.
"""

import json
import os
import re
import tempfile
import threading
import time

import requests

from tools.cache import ttl_cache

API_BASE = "https://api.elevenlabs.io"
# Defaults chosen from the current ElevenLabs docs: Flash v2.5 is the
# cheapest per-character TTS model; "George" is the voice used in the
# official quickstart. Both are overridable via env.
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_OUTPUT_FORMAT = "mp3_22050_32"
REQUEST_TIMEOUT_SECONDS = 30


class VoiceError(Exception):
    """Any voice failure. `str(e)` is always safe to show to a user."""


class MissingKeyError(VoiceError):
    pass


class CapReachedError(VoiceError):
    pass


def get_api_key() -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    return key or None


def get_voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)


def get_model_id() -> str:
    return os.environ.get("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)


def synthesize(text: str, voice_id: str | None = None, model_id: str | None = None) -> bytes:
    """Return MP3 bytes for `text`. Raises VoiceError (never leaks the key)."""
    text = (text or "").strip()
    if not text:
        raise VoiceError("There's nothing to read aloud.")
    key = get_api_key()
    if not key:
        raise MissingKeyError("Voice isn't configured (no ELEVENLABS_API_KEY).")

    try:
        resp = requests.post(
            f"{API_BASE}/v1/text-to-speech/{voice_id or get_voice_id()}",
            params={"output_format": DEFAULT_OUTPUT_FORMAT},
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": model_id or get_model_id()},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise VoiceError("Couldn't reach the voice service. Try again in a moment.") from None

    if resp.status_code != 200:
        raise VoiceError(_friendly_error(resp))
    return resp.content


def _friendly_error(resp: requests.Response) -> str:
    status = resp.status_code
    if status in (401, 403):
        return "The voice API key was rejected or lacks text-to-speech permission."
    if status == 429:
        return "The voice service is rate-limiting requests. Try again shortly."
    if status == 402:
        return "The voice service quota is used up for this period."
    if status == 422:
        return "The voice service couldn't process that text."
    return f"The voice service returned an error (HTTP {status})."


def timed_synthesize(text: str, **kwargs) -> tuple[bytes, float]:
    """synthesize() plus wall-clock seconds, for measurement."""
    start = time.perf_counter()
    audio = synthesize(text, **kwargs)
    return audio, time.perf_counter() - start


_MD_STRIP = re.compile(r"[*_`#>|]+")


def clean_for_speech(text: str, max_chars: int = 800) -> str:
    """Strip markdown, collapse whitespace, and hard-cap length at a
    sentence boundary where possible."""
    text = _MD_STRIP.sub("", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: last_stop + 1] if last_stop > max_chars // 2 else cut).strip()


# --- Caching, usage guard, quota ---------------------------------------

DEFAULT_MAX_CHARS = 800
DEFAULT_SESSION_LIMIT = 3
AUDIO_CACHE_TTL_SECONDS = 60 * 60

# Incremented only when a real API request is made, so callers can tell a
# cache hit (free) from a miss (costs credits) by comparing before/after.
api_call_count = 0


def get_max_chars() -> int:
    return int(os.environ.get("VOICE_MAX_CHARS", DEFAULT_MAX_CHARS))


def get_session_limit() -> int:
    return int(os.environ.get("VOICE_MAX_PER_SESSION", DEFAULT_SESSION_LIMIT))


# --- Global monthly character cap ----------------------------------------
# The session limit resets on a page refresh, so on its own it can't stop a
# few visitors from using up the whole free tier. This caps total characters
# sent to the API per calendar month (UTC) across ALL sessions of this app
# process, persisted to a small JSON file. Limitation: on hosts with an
# ephemeral filesystem (e.g. Streamlit Community Cloud) the file is lost when
# the container restarts, which resets the counter -- a safety net, not exact
# accounting. Only real API calls count; cache hits are free.

DEFAULT_GLOBAL_CAP = 8000
_usage_lock = threading.Lock()


def get_global_cap() -> int:
    return int(os.environ.get("VOICE_GLOBAL_CHAR_CAP", DEFAULT_GLOBAL_CAP))


def _usage_path() -> str:
    return os.environ.get("VOICE_USAGE_FILE") or os.path.join(tempfile.gettempdir(), "vacation_planner_voice_usage.json")


def _current_month() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def global_chars_used() -> int:
    """Characters sent this calendar month; 0 if unknown/corrupt/new month."""
    try:
        with open(_usage_path()) as f:
            data = json.load(f)
        return int(data["chars"]) if data.get("month") == _current_month() else 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 0


def _record_usage(chars: int) -> None:
    path = _usage_path()
    payload = {"month": _current_month(), "chars": global_chars_used() + chars}
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    except OSError:
        pass  # can't persist -> cap is best-effort, never break the feature


@ttl_cache(ttl_seconds=AUDIO_CACHE_TTL_SECONDS)
def _synthesize_cached(text: str, voice_id: str, model_id: str) -> bytes:
    global api_call_count
    with _usage_lock:
        if global_chars_used() + len(text) > get_global_cap():
            raise CapReachedError("This app's monthly voice budget is used up. Please check back next month.")
        api_call_count += 1
        audio = synthesize(text, voice_id=voice_id, model_id=model_id)
        _record_usage(len(text))
    return audio


def synthesize_cached(text: str) -> bytes:
    """Cached on (text, voice id, model id): the same summary never costs
    credits twice within the TTL. Errors are not cached."""
    return _synthesize_cached(text.strip(), get_voice_id(), get_model_id())


def fetch_quota() -> dict | None:
    """{'used', 'limit'} characters, or None if unavailable. Needs an API
    key with the user_read permission; any failure just means "don't show
    quota", never an error."""
    key = get_api_key()
    if not key:
        return None
    try:
        resp = requests.get(
            f"{API_BASE}/v1/user/subscription",
            headers={"xi-api-key": key},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {"used": int(data["character_count"]), "limit": int(data["character_limit"])}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
