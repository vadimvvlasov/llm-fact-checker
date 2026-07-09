"""Shared chat-model client: OpenRouter by default, local Ollama as a fallback."""

from langchain_openai import ChatOpenAI

from src.config import LLM_MODEL, LLM_PROVIDER, OLLAMA_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


def _client_kwargs() -> dict:
    # No explicit timeout -> openai client's 600s default. On OpenRouter's free
    # tier a congested upstream provider can make a single call take minutes;
    # fail fast there. Ollama's cold start (CPU-only, ~2 min) needs more room.
    if LLM_PROVIDER == "ollama":
        return {"base_url": OLLAMA_BASE_URL, "api_key": "ollama", "timeout": 180, "max_retries": 1}
    return {"base_url": OPENROUTER_BASE_URL, "api_key": OPENROUTER_API_KEY, "timeout": 30, "max_retries": 1}


def chat_llm(temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(model=LLM_MODEL, temperature=temperature, **_client_kwargs())
