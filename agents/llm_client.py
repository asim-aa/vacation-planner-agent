"""
Shared LLM client for the sub-agent nodes. Points at a self-hosted,
OpenAI-compatible endpoint (configured via .env) rather than a public
provider -- ChatOpenAI supports this via `base_url`.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        model=os.environ["LLM_MODEL"],
        timeout=float(os.environ.get("LLM_TIMEOUT_SECONDS", 120)),
        temperature=temperature,
    )
