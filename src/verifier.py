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
from src.llm import chat_llm

VERDICT_PROMPT_V1 = """You are a fact-checker. You're given a claim and a set of retrieved
evidence chunks from a knowledge base. Decide:

- VERIFIED: a chunk confirms the claim's entity, metric, and value (numbers can be rounded).
- REFUTED: a chunk covers the same entity and metric, but with a different value or fact.
- INSUFFICIENT: no chunk actually covers this entity + metric — don't guess from a
  loosely related chunk.

Quote the exact supporting/contradicting chunk text as `quote`, and its title as `source`.
For INSUFFICIENT, leave `source` and `quote` null."""


class Verdict(BaseModel):
    verdict: Literal["VERIFIED", "REFUTED", "INSUFFICIENT"]
    source: str | None = Field(description="Title of the chunk that decided the verdict, or null")
    quote: str | None = Field(description="Verbatim chunk text supporting the verdict, or null")


def _judge(prompt: str):
    return chat_llm().with_structured_output(Verdict), prompt


def verify_claim(claim: Claim, prompt: str = VERDICT_PROMPT_V1, top_k: int = 5) -> Verdict:
    with get_conn() as conn:
        embedding = embed_texts([claim.text])[0]
        chunks = hybrid_search(conn, claim.text, embedding, top_k=top_k)

    if not chunks:
        return Verdict(verdict="INSUFFICIENT", source=None, quote=None)

    evidence = "\n\n".join(f"[{c['title']}]\n{c['content']}" for c in chunks)
    user_message = (
        f"Claim: {claim.text}\n"
        f"(entity={claim.entity!r}, metric={claim.metric!r}, value={claim.value}, date={claim.date!r})\n\n"
        f"Retrieved evidence:\n{evidence}"
    )
    judge, prompt = _judge(prompt)
    return judge.invoke([("system", prompt), ("user", user_message)])
