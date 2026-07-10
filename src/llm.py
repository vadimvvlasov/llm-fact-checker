"""Shared chat-model client, provider selected via LLM_PROVIDER (see src/config.py)."""

from langchain_openai import ChatOpenAI

from src.config import LLM_MODEL, LLM_PROVIDER, LLM_PROVIDERS


def chat_llm(temperature: float = 0) -> ChatOpenAI:
    provider = LLM_PROVIDERS[LLM_PROVIDER]
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=temperature,
        base_url=provider["base_url"],
        api_key=provider["api_key"],
        timeout=provider["timeout"],
        max_retries=provider["max_retries"],
    )
