"""Keep voice-usage bookkeeping out of the real temp dir during tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_voice_usage_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_USAGE_FILE", str(tmp_path / "voice_usage.json"))
    monkeypatch.delenv("VOICE_GLOBAL_CHAR_CAP", raising=False)
