"""Shared chat-model client, provider selected via LLM_PROVIDER (see src/config.py)."""

from langchain_openai import ChatOpenAI

from src.config import LLM_MODEL, LLM_PROVIDER, LLM_PROVIDERS

# Token usage per structured call (see invoke_structured), for cost tracking —
# same shape as ChatOpenAI's usage_metadata: input_tokens/output_tokens/total_tokens.
USAGE_LOG: list[dict] = []


def chat_llm(temperature: float = 0) -> ChatOpenAI:
    provider = LLM_PROVIDERS[LLM_PROVIDER]
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=temperature,
        base_url=provider["base_url"],
        api_key=provider["api_key"],
        timeout=provider["timeout"],
        max_retries=provider["max_retries"],
        use_responses_api=True,
    )


def invoke_structured(schema, messages, temperature: float = 0):
    """Structured call (claim extraction, verdict) that also records usage in USAGE_LOG."""
    result = chat_llm(temperature).with_structured_output(schema, include_raw=True).invoke(messages)
    USAGE_LOG.append(result["raw"].usage_metadata)
    return result["parsed"]
