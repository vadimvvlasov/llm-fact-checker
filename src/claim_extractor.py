"""LLM extracts checkable factual claims (a number tied to an entity) from report text."""

from pydantic import BaseModel, Field

from src.llm import invoke_structured

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


def extract_claims(report_text: str) -> list[Claim]:
    result = invoke_structured(ClaimList, [("system", SYSTEM_PROMPT), ("user", report_text)])
    return result.claims
