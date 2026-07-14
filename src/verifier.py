"""LLM-as-judge: claim + retrieved evidence -> VERIFIED / REFUTED / INSUFFICIENT + citation.

`VERDICT_PROMPT_V1` is passed explicitly (not hardcoded) so Phase 3 can run a second
prompt variant against the same claims and compare accuracy — see the "LLM evaluation,
2 prompts" line in the capstone rubric.
"""

from typing import Literal

from pydantic import BaseModel, Field

from src.claim_extractor import Claim
from src.db import get_conn, hybrid_search
from src.embeddings import embed_texts
from src.llm import invoke_structured
from src.query_rewrite import rewrite_query
from src.rerank import rerank

VERDICT_PROMPT_V1 = """You are a fact-checker. You're given a claim and a set of retrieved
evidence chunks from a knowledge base. Decide:

- VERIFIED: a chunk confirms the claim's entity, metric, and value (numbers can be rounded).
- REFUTED: a chunk covers the same entity and metric, but with a different value or fact.
- INSUFFICIENT: no chunk actually covers this entity + metric — don't guess from a
  loosely related chunk.

Quote the exact supporting/contradicting chunk text as `quote`, and its title as `source`.
For INSUFFICIENT, leave `source` and `quote` null."""

VERDICT_PROMPT_V2 = """You are a fact-checker. You're given a claim and a set of retrieved
evidence chunks from a knowledge base.

Before deciding, work through it step by step in `reasoning`: which chunk (if any) covers
the same entity and metric as the claim, what value or fact it states, and how that
compares to the claim's value. Then decide:

- VERIFIED: a chunk confirms the claim's entity, metric, and value (numbers can be rounded).
- REFUTED: a chunk covers the same entity and metric, but with a different value or fact.
- INSUFFICIENT: no chunk actually covers this entity + metric — don't guess from a
  loosely related chunk.

Quote the exact supporting/contradicting chunk text as `quote`, and its title as `source`.
For INSUFFICIENT, leave `source` and `quote` null."""


class Verdict(BaseModel):
    reasoning: str = Field(description="Brief step-by-step reasoning, before deciding the verdict")
    verdict: Literal["VERIFIED", "REFUTED", "INSUFFICIENT"]
    source: str | None = Field(description="Title of the chunk that decided the verdict, or null")
    quote: str | None = Field(description="Verbatim chunk text supporting the verdict, or null")


def verify_claim(
    claim: Claim,
    prompt: str = VERDICT_PROMPT_V1,
    top_k: int = 5,
    rerank_k: int = 3,
    search_query: str | None = None,
) -> Verdict:
    """search_query: pass a precomputed rewrite_query(claim.text) result to skip
    rewriting here — e.g. eval/ragas_eval.py needs the same rewritten query for both
    retrieving RAGAS's evidence and for this call, and shouldn't pay for rewriting twice."""
    search_query = search_query or rewrite_query(claim.text)
    with get_conn() as conn:
        embedding = embed_texts([search_query])[0]
        chunks = hybrid_search(conn, search_query, embedding, top_k=top_k)
    chunks = rerank(search_query, chunks, top_k=rerank_k)

    if not chunks:
        return Verdict(
            reasoning="No chunks retrieved from the knowledge base for this claim.",
            verdict="INSUFFICIENT",
            source=None,
            quote=None,
        )

    evidence = "\n\n".join(f"[{c['title']}]\n{c['content']}" for c in chunks)
    user_message = (
        f"Claim: {claim.text}\n"
        f"(entity={claim.entity!r}, metric={claim.metric!r}, value={claim.value}, date={claim.date!r})\n\n"
        f"Retrieved evidence:\n{evidence}"
    )
    return invoke_structured(Verdict, [("system", prompt), ("user", user_message)])
