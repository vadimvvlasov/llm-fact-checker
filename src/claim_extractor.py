"""LLM extracts checkable factual claims (a number tied to an entity) from report text."""

from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config import LLM_MODEL, LLM_PROVIDER, OLLAMA_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

SYSTEM_PROMPT = """You extract checkable factual claims from business report text.

A claim ties a specific entity to a numeric metric: a company's revenue, net income,
or total assets for a fiscal period; a country's GDP, inflation, or unemployment rate;
or a similar quantitative fact with a date attached. Skip opinions, forward-looking
statements, and sentences with no number in them.

For each claim, keep the original sentence as `text`, and also pull out the entity,
metric, numeric value, and date/period separately so each field can be checked against
a source independently."""


class Claim(BaseModel):
    text: str = Field(description="The claim as written in the report, verbatim")
    entity: str = Field(description="Company name/ticker or country the claim is about")
    metric: str = Field(description="What's being measured, e.g. Revenue, GDP, Net income")
    value: float | None = Field(description="The numeric value claimed, or null if not extractable")
    date: str | None = Field(description="Date, fiscal year end, or period the claim refers to")


class ClaimList(BaseModel):
    claims: list[Claim]


def _llm_kwargs() -> dict:
    if LLM_PROVIDER == "ollama":
        return {"base_url": OLLAMA_BASE_URL, "api_key": "ollama"}
    return {"base_url": OPENROUTER_BASE_URL, "api_key": OPENROUTER_API_KEY}


@lru_cache(maxsize=1)
def _structured_llm():
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0, **_llm_kwargs())
    return llm.with_structured_output(ClaimList)


def extract_claims(report_text: str) -> list[Claim]:
    result = _structured_llm().invoke([("system", SYSTEM_PROMPT), ("user", report_text)])
    return result.claims
