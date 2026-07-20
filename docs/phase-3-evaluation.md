# Phase 3 — Hybrid Search + Evaluation

**Status: done.** Retrieval, reranking, LLM-judge prompts, and query
rewriting are all implemented and measured. Full transcripts and code:
`notebooks/phase3_evaluation.ipynb`.

## Metrics

- **hit_rate@k** — did the correct document appear in the top-k results?
- **MRR@k** — how high did it rank? 1st place scores 1.0, 2nd scores 0.5, and so on.
- **Faithfulness** (RAGAS) — does the verdict trace back to the retrieved evidence?
- **Context precision** (RAGAS) — was the retrieved evidence actually relevant?
- **Accuracy** — does the verdict match the labeled answer in `data/eval_claims.csv`?

## Retrieval evaluation

Tested on 68 labeled claims (`eval/compare_retrieval.py`):

| Method | hit_rate@5 | MRR@5 |
|---|---|---|
| minsearch | 85% | 0.853 |
| Postgres full-text | 78% | 0.664 |
| pgvector | 88% | 0.873 |
| hybrid (RRF) | 90% | 0.860 |
| **hybrid + rerank** | **90%** | **0.890** |

Hybrid search + cross-encoder reranking wins — it's the path `verify_claim()`
uses. Reranking (`src/rerank.py`, `cross-encoder/ms-marco-MiniLM-L-6-v2`)
only rescores the top-5 candidates hybrid search already found, not the
whole knowledge base.

The 7 remaining misses are all FRED claims — a source collision, not a
vocabulary gap ("US GDP in Q3 2019" retrieves World Bank's GDP instead of
FRED's). Query rewriting (below) targets this directly.

## LLM judge evaluation

Two prompts compared on the full 76-claim set (`eval/ragas_eval.py`):

| Prompt | Accuracy | Faithfulness | Context precision |
|---|---|---|---|
| **`VERDICT_PROMPT_V1`** | **79%** (60/76) | 0.748 | **0.669** |
| `VERDICT_PROMPT_V2` | 74% (56/76) | 0.747 | 0.587 |

`VERDICT_PROMPT_V1` wins on accuracy and context precision, ties on
faithfulness — it's `verifier.py`'s default. `V2` asks the judge to reason
step by step first, which produces more `INSUFFICIENT` verdicts and lower
accuracy.

(RAGAS's faithfulness score is `NaN` for verdicts with no clear factual
statement, mostly `INSUFFICIENT` — fixed in `eval/ragas_eval.py` to drop
`NaN` instead of summing it into the average.)

## Query rewriting

`src/query_rewrite.py` uses an LLM to rewrite the claim into a clearer
search query before retrieval, naming the likely source when the claim is
ambiguous. Wired into `verify_claim()` by default.

| Method | hit_rate@5 | MRR@5 |
|---|---|---|
| no rewrite (baseline) | 90% (61/68) | 0.860 |
| with rewrite (`granite4.1:3b`) | **93%** (63/68) | 0.909* |

*MRR@3, after reranking — the path `verify_claim()` actually uses.

Retrieval genuinely improves (61→63 of 68 docs found, better ranking). Final
verdict accuracy on the 7 hardest cases doesn't: 2/7 correct either way, but
not the same 2 claims — rewriting fixes one and breaks a different one.

### Does the rewrite model matter?

Tested 3 more local LLMs for the rewrite step (`ornith:latest`, 9B, timed
out twice — dropped):

| Model | hit_rate@5 | MRR@3 (reranked) |
|---|---|---|
| no rewrite | 90% | 0.890 |
| `granite4.1:3b` | 93% | 0.909 |
| `laguna-xs-2.1` (33B) | 91% | 0.890 |
| `granite4.1:8b` | **96%** | **0.934** |

Final verdict correctness, on the 7 claims that miss without rewriting:

| Model | without rewrite | with rewrite |
|---|---|---|
| `granite4.1:3b` | 2/7 | 2/7 |
| `laguna-xs-2.1` | 1/7 | **3/7** |
| `granite4.1:8b` | **3/7** | 2/7 |

**Key finding: better retrieval doesn't mean a better final answer.**
`granite4.1:8b` has the best retrieval score and the worst verdict outcome;
`laguna-xs-2.1` has the worst retrieval score and the best verdict outcome.
Small sample (7 claims), but a repeatable pattern across all 3 models.

## Production recommendation

- **Local (Ollama, CPU, free): `granite4.1:3b`.** Improves retrieval,
  doesn't hurt verdict correctness, fast. Ships as the default.
  `granite4.1:8b` was ruled out despite better retrieval (worse verdicts);
  `laguna-xs-2.1` despite the best verdict outcome (too slow on CPU,
  75-100s/call).
- **Cloud (hosted API): `laguna-xs-2.1`.** Best verdict outcome of the
  three — a hosted API removes the CPU-latency problem that ruled it out
  locally. Not confirmed via the hosted API itself, only the local build.

Either way, `.env`'s actual provider (OpenRouter's free tier) already hits
its daily quota sometimes — a real deployment needs a paid tier regardless
of which model runs on it.

[← Back to README](../README.md)
