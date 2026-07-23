"""LLM rewrites a claim into a search query before retrieval.

Motivated by a concrete miss in `docs/phase-3-evaluation.md`: "US GDP in the third
quarter of 2019..." retrieves World Bank's cross-country GDP series instead of FRED's
US-specific GDP series -- same concept, different source, close enough lexically that
hybrid search picks the wrong one. Rewriting adds a source-type disambiguator so
retrieval has more to match against than the bare claim text.
"""

import logging

from pydantic import BaseModel, Field

from src.llm import invoke_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You rewrite a factual claim into a search query for a hybrid
(keyword + vector) search over a knowledge base with four source types:

- Wikipedia: definitional/background articles (e.g. "Bear market", "Inflation")
- World Bank: cross-country economic indicators (GDP, inflation, unemployment), one
  series per country, comparable across countries
- FRED: US-specific macroeconomic time series from the Federal Reserve (GDP, interest
  rates, unemployment, CPI)
- SEC EDGAR: company 10-K filings (revenue, net income, total assets)

Some claims are ambiguous between World Bank and FRED -- e.g. "US GDP" could be either
series, even though only one is the actual source. Rewrite the claim as a concise
search query that keeps the entity, metric, and date, and adds a short disambiguating
phrase naming which source most plausibly holds this fact (e.g. "Federal Reserve
economic data series", "World Bank cross-country indicator", "SEC 10-K filing",
"Wikipedia article") when the claim could plausibly match more than one source type.
Don't invent numbers or facts, only rephrase for retrieval."""


class RewrittenQuery(BaseModel):
    query: str = Field(
        description="Rewritten search query: entity + metric + date preserved, "
        "disambiguated by source type where the claim is ambiguous"
    )


def rewrite_query(claim_text: str) -> str:
    """Best-effort: falls back to the raw claim text if the rewrite call fails
    (e.g. a flaky free-tier LLM returning a malformed response) rather than
    failing the whole verification — retrieval on the unrewritten claim still works,
    just without the source-type disambiguation this adds."""
    try:
        result = invoke_structured(RewrittenQuery, [("system", SYSTEM_PROMPT), ("user", claim_text)])
        return result.query
    except Exception:
        logger.warning("rewrite_query failed, falling back to raw claim text", exc_info=True)
        return claim_text
