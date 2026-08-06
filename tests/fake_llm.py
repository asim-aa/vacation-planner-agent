"""
Fake LLM for tests. Mimics the one method the agent nodes call
(`llm.invoke(prompt)` -> object with a `.content` attribute) without
touching the network or the self-hosted endpoint.

Use FakeLLM("some canned response") for agent-node tests that don't care
what the LLM says. Use RecordingFakeLLM to also assert on what prompt the
node actually sent.
"""

from dataclasses import dataclass


@dataclass
class _FakeResponse:
    content: str


class FakeLLM:
    def __init__(self, response_text: str = "This is a great pick."):
        self.response_text = response_text

    def invoke(self, prompt: str) -> _FakeResponse:
        return _FakeResponse(content=self.response_text)


class RecordingFakeLLM(FakeLLM):
    def __init__(self, response_text: str = "This is a great pick."):
        super().__init__(response_text)
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> _FakeResponse:
        self.prompts.append(prompt)
        return super().invoke(prompt)
