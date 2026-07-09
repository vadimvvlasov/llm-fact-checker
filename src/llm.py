"""Shared chat-model client: OpenRouter by default, local Ollama as a fallback."""

from langchain_openai import ChatOpenAI

from src.config import LLM_MODEL, LLM_PROVIDER, OLLAMA_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


def _client_kwargs() -> dict:
    if LLM_PROVIDER == "ollama":
        return {"base_url": OLLAMA_BASE_URL, "api_key": "ollama"}
    return {"base_url": OPENROUTER_BASE_URL, "api_key": OPENROUTER_API_KEY}


def chat_llm(temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(model=LLM_MODEL, temperature=temperature, **_client_kwargs())
