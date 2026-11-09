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

## Deployed app (Streamlit Community Cloud) -- owner-reported
Results below were reported by the owner after running the public app; I could not reach it from my sandbox, so none of it is measured by me.

**What broke first**
- With the key added to Streamlit secrets, the button showed only "The voice service returned an error (HTTP 400)". The ElevenLabs Request Log showed no text-to-speech request for it (only dashboard page loads), so ElevenLabs had not logged it.
- My first theory (blank optional settings such as an empty voice or model id overriding the defaults) was **wrong for this case** -- the owner had no optional settings. The fix still went in as hardening (blank/invalid values now fall back to defaults; previously a blank numeric setting would have crashed).
- Real cause: the owner had pasted the API key **ID** instead of the secret key (`sk_...`). After PR #4 made the app show ElevenLabs' own message, it read: "API key ID used as API key - only valid API keys can be used. API keys start with 'sk_' ...". Rotating the key and pasting the `sk_` value fixed it.
- Lesson: the first error message was too vague to diagnose a configuration mistake; surfacing the provider's own error text (and a snippet for non-JSON replies) turned a guess into a one-step fix.

**After the fix (owner's words)**
- Audio plays and the entire summary played.
- Sounded "a bit robotic"; covered everything well; accurate (no invented details noticed).
- Cache on the deployed app: the owner re-ran it on the same itinerary and reported the credits **stayed the same** (consistent with a cache hit; I did not see the exact before/after numbers or the timing of the repeat).
- Timing: reported as "instant" -- not specified whether that was the first generation or a repeat click, and no seconds were measured.
- Credits, from the dashboard (before 400 / after 615 of 10,000, Free plan): the deployed generation cost **215 credits**. At ~0.5 credits/char that is about 430 characters, a typical summary length -- an inference from the rate, since I did not see the summary's character count. The failed attempts (rejected at authentication) are not visible as credit use.

**Not reported / not checked**
- Whether the spoken text came from the LLM or the templated fallback.
- Failure tests with real conditions (wrong key beyond the key-ID case, wifi off, empty/very long itinerary), session-limit behavior on the live app, and a browser dev-tools check on the *deployed* app that the key never reaches the browser (done locally -- see "Local browser run" below).
- Voice quality beyond "a bit robotic"; I have not listened to any audio. A different voice or settings might sound less robotic; not tried.

## Follow-up: what the first real LLM summary got wrong (owner's screenshot)
The owner's deployed run (430 characters, audio 0:26, caption "430 characters in 0.7s") settled which writer produced the text: the **LLM**, not the template (first-person phrasing, "From New York, I flew to Paris..."). The spoken text had three real problems:
1. **Wrong perspective/tense.** It said "I flew", "I planned", "I visited" for a trip that hasn't happened. My prompt never said the trip was upcoming or to address the traveler -- a prompt bug.
2. **An embellishment not in the facts.** "The trip was a memorable blend of history, art, and local culture." Nothing in the facts supports it. The place-name guard did not catch it because it only checks for invented *cities* -- the limitation I had logged earlier, now seen in a real output.
3. **Numbers that may not reconcile.** It said "about three hundred fifty dollars each way, totaling about seven hundred thirty dollars" (2 x 350 is 700). I could not see the trip's data, so I don't know whether the model misstated a figure or rounding caused it; I only know the spoken sentence is internally inconsistent. The owner had called the summary "accurate" before seeing this closely.
Also: the "0.7s" caption times only the ElevenLabs request, not the LLM call, so it is not click-to-audio latency (still unmeasured).

**Changes made:** the prompt now says the trip is upcoming, requires second person and future tense, forbids opinions/descriptions/closing remarks, and tells the model not to do arithmetic; the round-trip flight total is now computed in code and passed as a fact (`flight_total_round_trip`); the UI now shows who wrote the text ("Written by the AI model" or a template caption saying why it fell back), because the fallback used to be silent. 6 new tests (plus an added assertion in an existing UI test).
**Not verified:** none of these prompt changes has been run against the real LLM, so I don't know yet that the model obeys them; a prompt can still be ignored. There is still no check on numbers or on non-city invented claims in the spoken text.

## Follow-up: second deployed run fell back to the template
After the prompt fix was deployed, the owner's next run (223 characters, audio 0:17, "223 characters in 0.7s") showed the new caption: **"Written from a template (the AI model was unavailable)"**. So the LLM call failed or returned nothing, and the app fell back. The text was consistent (846 dollars each way, 1692 total, inside a 2500 budget), but spoke "Delta + American (self-connect via ORD)" -- an airport code read as letters, and a "+".
- **Why the LLM failed: unknown.** The old code swallowed the error and showed no reason. The owner has since said they no longer have access to the LLM endpoint, so the deployed app can no longer produce AI-written summaries.
- **Consequence for what can be claimed:** the only AI-written summary I know of was the earlier run (first-person, past tense, one unsupported sentence). **The fixed prompt has never been run against the real LLM**, so I cannot say whether it fixes those problems. On the deployed app the summary is the template.
- **Changes made:** the fallback caption now includes the error *type* (never the message, which can echo secrets) or "empty reply"; `VOICE_SUMMARY_USE_LLM=false` skips the LLM call entirely (no failed call, no waiting on a dead endpoint) with its own caption; the airline label is made speakable ("Delta and American, connecting yourself in Chicago", via the offline airport lookup) before reaching either the template or the LLM prompt. 10 new tests; suite: 162 passed, 11 skipped.
- **Not verified:** the disabled mode and the new airline wording have only run in tests, not on the deployed app. A second side effect worth noting: the old (pre-fix) behavior could not have mentioned the connection city without tripping the guard; the cleaned airline name now puts it in the allowed set (tested with a fake LLM only).

## Local browser run (headless Chromium, run by me in the sandbox)
Setup: the real `app.py`, unchanged, with a **preloaded fixture trip** (the test suite's Paris trip: Delta nonstop $300, Test Hotel $80/night, Eiffel Tower -- not real search data), `VOICE_SUMMARY_USE_LLM=false`, and a real ElevenLabs call. A placeholder key value was set locally and the real key was injected by the sandbox's network proxy, so the browser-exposure search below used the placeholder string. One click on "Generate audio summary".
- **Click to audio: 1835 ms**, measured in the browser (click to the audio player appearing, including the Streamlit rerun). The app's own caption read "272 characters in 1.0s" (the ElevenLabs request only). One sample, from a sandbox whose network is slower than a laptop's, and with the template summary, so it contains no LLM time -- it is not a deployed-app or LLM-path latency.
- **Caption shown:** "Written from a template (AI summaries are turned off)". Spoken text was the template: "Here's your 6 day trip to Paris, France in April. You'll fly Delta, nonstop, for about 300 dollars each way..." (second person, future tense, no codes).
- **Key exposure: not found.** I searched the page HTML, the visible text, and all 541 network lines the browser saw (requests, responses, and WebSocket frames) for `xi-api-key`, `ELEVENLABS`, `sk_` and the placeholder key value: zero matches. The browser made zero requests to `elevenlabs.io`; the audio was served from the app's own local `/media/...` URL. This shows the key stays server-side in this code path; it is not a check of the deployed app, and it used a placeholder value.
- **Cost:** two real calls of 272 characters each (about 544 characters; roughly 272 credits at the ~0.5 credits/char rate -- an inference, I did not read the dashboard). The first attempt's click went through but my script crashed on a hidden duplicate `<audio>` element before recording timing, so I restarted the server (clearing the in-memory cache) and ran it again for the measurement.
- **Not tested in this run:** a wrong key, wifi off, an empty or very long itinerary, the per-session limit in a browser, the LLM path, and the deployed app.

## Deployed app after the LLM was gone (owner-reported, two screenshots)
- **A deployment ImportError.** After the follow-up PRs merged, the owner's public app showed `ImportError` at `app.py` line 26 (the import of `build_voice_summary_with_source` and `describe_source` from `agents.voice_summary`). I checked that `main` itself was fine: a clean export of the merged commit imported both names without error. The owner used **Reboot app** and it worked. **Root cause not confirmed**; my best guess is that Streamlit Cloud kept the old `agents/voice_summary.py` module in memory while `app.py` reloaded, but I could not see the deployment or its logs.
- **Live run with `VOICE_SUMMARY_USE_LLM = "false"`.** Caption: "Written from a template (AI summaries are turned off)". Caption under the player: "192 characters in 0.5s" (the ElevenLabs request only, not click-to-audio). Audio length 0:13. Spoken text: "Here's your 6 day trip to Paris, France in April. You'll fly Aer Lingus, with 1 stop, for about 350 dollars each way. Your estimated total is about 700 dollars, inside your 2500 dollar budget." The owner said the template looked fine. Credits for this run: about 96 at the inferred ~0.5 credits/char rate; the dashboard was not read.
- **Two observations I did not investigate.** (1) This summary mentions only the flight and the total -- no hotel or activities -- and the 700 total equals 2 x 350, so this trip's data seems to have had no lodging or activity cost; I don't know why. (2) The earlier AI-written summary for what looked like the same trip said "totaling about seven hundred thirty dollars" for the flight, while 2 x 350 is 700 and the app's own total now says 700; that suggests the model misstated the figure, but live prices can change, so I cannot confirm it was the same data.
- **Still not checked:** a dev-tools search for the key on the deployed app, real failure cases (wifi off, empty or very long itinerary), and the per-session limit on the live app.
