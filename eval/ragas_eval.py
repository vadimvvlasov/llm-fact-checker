"""RAGAS + LLM-as-judge evaluation of verify_claim() against data/eval_claims.csv.

Compares VERDICT_PROMPT_V1 vs VERDICT_PROMPT_V2 (src/verifier.py) on two axes:
- verdict accuracy — our own metric, verdict.verdict vs expected_verdict
- RAGAS faithfulness / context precision — does the judge's verdict+quote actually
  follow from the retrieved evidence, not the model's own knowledge

Runs on a random sample by default — one verify_claim call is a real LLM round-trip
(~10-60s on free-tier providers), so the full 76-claim set x 2 prompts is a lot of
wall-clock time. Pass sample_size=None for the full set.
"""

import asyncio
import csv
import random
from pathlib import Path

from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import ContextPrecisionWithoutReference, Faithfulness

from src.claim_extractor import Claim
from src.config import LLM_MODEL, LLM_PROVIDER, LLM_PROVIDERS
from src.db import get_conn, hybrid_search
from src.embeddings import embed_texts
from src.query_rewrite import rewrite_query
from src.rerank import rerank
from src.verifier import VERDICT_PROMPT_V1, VERDICT_PROMPT_V2, verify_claim

EVAL_CSV = Path(__file__).resolve().parent.parent / "data" / "eval_claims.csv"
SAMPLE_SIZE = 10
SEED = 42


def load_claims() -> list[dict]:
    with open(EVAL_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def retrieve_contexts(search_query: str) -> list[dict]:
    """Same rewrite -> retrieve -> rerank path verify_claim() uses internally, kept
    separate here so this script can hand the retrieved chunks to RAGAS (verify_claim
    only returns the verdict, not the evidence it was judged against). Takes the
    already-rewritten query, not the raw claim text — score_claim() rewrites once and
    passes the same search_query to both this function and verify_claim(), so a claim
    isn't rewritten twice (rewrite_query is itself an LLM call)."""
    embedding = embed_texts([search_query])[0]
    with get_conn() as conn:
        chunks = hybrid_search(conn, search_query, embedding, top_k=5)
    return rerank(search_query, chunks, top_k=3)


def ragas_llm():
    provider = LLM_PROVIDERS[LLM_PROVIDER]
    # timeout: the openai client's 600s default means a stuck free-tier call just
    # hangs silently — same lesson as src/llm.py, easy to forget on a second client.
    # max_retries=5: Groq's free-tier TPM (tokens-per-minute) limit means back-to-back
    # calls within the same claim's scoring (verify + faithfulness + context_precision)
    # can hit a transient 429 even under budget overall — instructor's own tenacity
    # retry loop backs off and retries on this, but only if given retries to spend.
    client = AsyncOpenAI(base_url=provider["base_url"], api_key=provider["api_key"], timeout=provider["timeout"], max_retries=5)
    # max_tokens: Groq's free tier caps at 8000 tokens/minute total (prompt + all
    # completions), so keep completions small there. Other providers don't have that
    # ceiling, but some free models ramble and truncate mid-generation at low limits
    # (instructor.IncompleteOutputException) — give them more room.
    max_tokens = 2048 if LLM_PROVIDER == "groq" else 8192
    return llm_factory(LLM_MODEL, client=client, max_tokens=max_tokens)


async def score_claim(row: dict, prompt: str, faithfulness: Faithfulness, context_precision: ContextPrecisionWithoutReference) -> dict | None:
    claim = Claim(text=row["claim"], entity="", metric="", value=None, date=None)
    search_query = rewrite_query(claim.text)
    chunks = retrieve_contexts(search_query)
    try:
        verdict = verify_claim(claim, prompt=prompt, search_query=search_query)
    except Exception as e:
        print(f"  [{row['id']}] SKIPPED — verify_claim failed: {str(e)[:150]}")
        return None

    result = {
        "id": row["id"],
        "correct": verdict.verdict == row["expected_verdict"],
        "faithfulness": None,
        "context_precision": None,
    }

    if chunks:
        contexts = [c["content"] for c in chunks]
        response = f"{verdict.verdict}: {verdict.quote or verdict.reasoning}"
        try:
            f = await faithfulness.ascore(user_input=claim.text, response=response, retrieved_contexts=contexts)
            cp = await context_precision.ascore(user_input=claim.text, response=response, retrieved_contexts=contexts)
            result["faithfulness"] = f.value
            result["context_precision"] = cp.value
        except Exception as e:
            print(f"  [{row['id']}] RAGAS scoring failed (verdict counted, faithfulness/precision skipped): {str(e)[:150]}")

    ok = "correct" if result["correct"] else "wrong"
    print(f"  [{row['id']}] {ok}, verdict={verdict.verdict} (expected {row['expected_verdict']}), "
          f"faithfulness={result['faithfulness']}, context_precision={result['context_precision']}")
    return result


async def run_prompt(name: str, prompt: str, claims: list[dict]) -> None:
    llm = ragas_llm()
    faithfulness = Faithfulness(llm=llm)
    context_precision = ContextPrecisionWithoutReference(llm=llm)

    print(f"--- {name} ---")
    raw_results = [await score_claim(row, prompt, faithfulness, context_precision) for row in claims]
    results = [r for r in raw_results if r is not None]
    skipped = len(raw_results) - len(results)

    n = len(results)
    accuracy = sum(r["correct"] for r in results) / n
    scored = [r for r in results if r["faithfulness"] is not None]
    avg_faithfulness = sum(r["faithfulness"] for r in scored) / len(scored) if scored else float("nan")
    avg_context_precision = sum(r["context_precision"] for r in scored) / len(scored) if scored else float("nan")

    skip_note = f", {skipped} skipped (verify_claim failed)" if skipped else ""
    print(f"{name}: accuracy={accuracy:.0%} ({sum(r['correct'] for r in results)}/{n})   "
          f"faithfulness={avg_faithfulness:.3f}   context_precision={avg_context_precision:.3f}   "
          f"(scored {len(scored)}/{n}{skip_note})\n")


def main(sample_size: int | None = SAMPLE_SIZE) -> None:
    claims = load_claims()
    if sample_size is not None and sample_size < len(claims):
        random.seed(SEED)
        claims = random.sample(claims, sample_size)
        print(f"sampled {sample_size}/{len(load_claims())} claims (seed={SEED}) — pass sample_size=None for the full set\n")
    else:
        print(f"evaluating on the full {len(claims)}-claim set\n")

    asyncio.run(run_prompt("VERDICT_PROMPT_V1", VERDICT_PROMPT_V1, claims))
    asyncio.run(run_prompt("VERDICT_PROMPT_V2", VERDICT_PROMPT_V2, claims))


if __name__ == "__main__":
    main()
