# Build log: ElevenLabs voice summary

Only things that actually happened. Nothing here is estimated.

## What was built
- `tools/voice.py`: thin ElevenLabs text-to-speech client (plain `requests`, one endpoint), speech-text cleanup, audio cache, per-session limit settings, optional quota lookup.
- `agents/voice_summary.py`: builds a short spoken summary from a small facts block taken from the trip state (not the Markdown itinerary). Output goes through the existing `narrative_guard`; falls back to a templated summary if the LLM fails or names a city that isn't part of the trip.
- `app.py`: `render_voice()` under the itinerary download button. Audio is generated only on button click; max 3 generated summaries per browser session (cache hits don't count).
- Config: `ELEVENLABS_API_KEY` (+ optional voice/model/limits) read from `st.secrets` or the environment. `.streamlit/secrets.toml` added to `.gitignore` before use; `.streamlit/secrets.toml.example` added. No key value appears anywhere in the repo.

## Choices and why
- **Plain `requests`, not the `elevenlabs` SDK.** One endpoint, `requests` already a dependency, one `requests.post` to mock in CI. The ElevenLabs onboarding CLI suggests the SDK; I didn't need it.
- **Endpoint:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`, `xi-api-key` header (docs: elevenlabs.io/docs/api-reference/text-to-speech/convert).
- **Model `eleven_flash_v2_5`:** the models page (elevenlabs.io/docs/overview/models) lists it as 50% lower price per character, 40,000-character limit.
- **Voice "George" (`JBFqnCBsd6RMkjVDRZzb`):** the voice used in the official quickstart (elevenlabs.io/docs/eleven-api/quickstart). I could not list voices myself (see problems), so this is the documented example voice, not a tuned choice.
- **Output `mp3_22050_32`:** the format used in the docs' Flash example; smallest/cheapest of the MP3 options I looked at. Not compared by ear.

## Real problems and how they resolved
1. **Docs host unreachable.** `elevenlabs.io` failed DNS from this sandbox (`ENOTFOUND`), and the GitHub tarball of ElevenLabs skills returned 403. I read the docs through a different fetch tool instead, and wrote the code from those pages (no ElevenLabs skill pack was used).
2. **API key is permission-restricted.** `GET /v1/user/subscription` and `GET /v1/voices` both returned `missing_permissions` (`user_read`, `voices_read`). Text-to-speech itself worked. Consequence: **live quota display is implemented but has never been exercised against the real API**; it is tested only with mocks, and quietly hides itself if the key lacks `user_read`.
3. **No LLM endpoint configured here** (`LLM_*` unset), so the LLM-written summary path was only run against a fake LLM. Real summary quality and length from the actual model are **unverified**.
4. **Dependencies weren't installed** in the sandbox; installed `requirements.txt` to run the suite.

## Measurements
- Test suite: baseline **102 passed, 11 skipped**; now **131 passed, 11 skipped** (+29 new tests; all ElevenLabs calls mocked; CI needs no secret).
- One real test call: 400 characters in, 91,132 bytes of MP3 out, **0.98 s** wall clock for one request (`eleven_flash_v2_5`, `mp3_22050_32`, George). That text was hand-written from the test fixture's trip, not LLM-generated.
- Cache, measured in one process with the same 400-character text: miss **1018 ms** (a real API call), hit **0.02 ms** (no API call; the call counter stayed at 1). One sample each, not an average.
- Characters consumed against the quota during testing: **800** (two real calls of 400 characters: the first test call and the cache-timing miss).
- Credits, read from the ElevenLabs dashboard (Free plan, 10,000 credits): **400 credits used** after those two calls. 800 characters sent, so this fits Flash v2.5 costing about **0.5 credits per character** (the models page says 50% lower price per character). That rate is inferred from one combined total, not measured per call; a single call is ~200 credits by that arithmetic. The free tier's 10,000 is in credits, not characters, so it is about 20,000 Flash characters.
- I did not listen to the audio (no audio output here), so voice quality and pronunciation are **unjudged**; the file is a valid MP3 by its `ID3` header only.

## Known limitations
- The narrative guard only catches invented *cities*, not invented prices or other details; the rest relies on the prompt.
- The per-session limit is per Streamlit session, so a page refresh resets it. It is a courtesy guard, not abuse protection. The cache is in-memory and per-process.
- The Streamlit UI was exercised through Streamlit's `AppTest`, not a real browser.
- Ruff isn't configured in this repo: 22 findings at baseline, 25 now (new ones are nested-`with` style nits in tests). CI doesn't run ruff.
- Nothing is committed or pushed.

## What I'd change next
- Use the real LLM once configured and look at the real summaries for length and pronunciation of names and prices.
- Measure real cache-hit vs. miss and compare output formats/models by ear.
- Move the usage guard server-side (per IP or global daily cap) if the public app gets traffic.

## Follow-up: global monthly cap
- Free-tier limit confirmed by the owner: 10,000 credits/month (dashboard); at ~0.5 credits/char for Flash that's ~20,000 characters, so the 8,000-character cap below leaves a wide margin. Per-session cap alone can't protect it (a page refresh resets it), so added `VOICE_GLOBAL_CHAR_CAP` (default 8,000), counted only on real API calls (cache hits and failed calls are free), persisted to a JSON file and reset each UTC month.
- Limitation: on an ephemeral filesystem (Streamlit Community Cloud) a container restart resets the counter, so this is a safety net, not exact accounting. It also only counts this app's own calls, not other uses of the same key.
- Tests: 139 passed, 11 skipped (8 new). `tests/test_app.py::test_app_loads_without_error` failed once on the first full run (AppTest RuntimeError, likely a cold-start timeout) and passed on isolated rerun and two more full runs; cause not root-caused.
