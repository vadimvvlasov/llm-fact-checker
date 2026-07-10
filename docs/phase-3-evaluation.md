# Phase 3 — Hybrid Search + Evaluation

**Status: in progress.** Reranker built and demoed
(`notebooks/phase3_evaluation.ipynb`); RAGAS eval and query rewriting still open.

## Goal

Make retrieval better, then measure how much better — hit-rate/MRR per
retrieval strategy, plus RAGAS + LLM-as-judge scores comparing baseline vs
hybrid vs hybrid+rerank.

**Metrics used in this doc, plainly:**

- **hit_rate@k** — fraction of claims where the correct document appeared
  somewhere in the top-k retrieved results (`hits / total`).
- **MRR@k** (Mean Reciprocal Rank) — same claims, scored by how high the
  correct document ranked: `1/rank` per claim (1st place = 1.0, 2nd = 0.5,
  3rd = 0.33...), averaged. Two strategies can tie on hit_rate but differ on
  MRR — hit_rate says "found it somewhere in the top-k", MRR says "found it
  near the top vs. barely made the cut."
- **Faithfulness** (RAGAS) — does the judge's verdict+quote actually trace
  back to the retrieved evidence, or did it add something the evidence
  doesn't say (0-1, 1 = fully grounded in the evidence).
- **Context precision** (RAGAS) — was the retrieved evidence actually
  relevant to the claim, or noise the judge had to ignore (0-1, 1 = all
  retrieved chunks relevant).
- **Accuracy** — our own metric, not RAGAS: does `verdict.verdict` match
  the labeled `expected_verdict` in `data/eval_claims.csv`.

## Why a cross-encoder reranker

`hybrid_search` (Phase 2) uses a **bi-encoder**: the query and each chunk are
embedded separately, into independent vectors, compared by cosine distance.
That's what makes it fast — chunk embeddings are precomputed once and reused
for every future query; at search time you only embed the query and compare
it against vectors already sitting in the database.

A **cross-encoder** works differently: query and chunk are concatenated into
one sequence and passed through the transformer together, so self-attention
sees both texts at once and can match specific words directly (e.g. "revenue"
in the claim against "Revenue" in the chunk), instead of each text being
compressed into a single vector first. It outputs one relevance score per
pair — more accurate, but the score only exists for that specific
(query, chunk) pair, so it can't be precomputed like an embedding.

That cost is why it's a second stage, not a replacement: `hybrid_search`
cheaply narrows the whole knowledge base down to a handful of candidates
(top-5), and the cross-encoder — too expensive to run against every chunk in
the database — only has to score those few pairs to pick the best top-3.

`src/rerank.py`: `rerank(query, chunks, top_k=3)`,
`cross-encoder/ms-marco-MiniLM-L-6-v2` (sentence-transformers, already a
dependency).

## Task breakdown

- [x] Cross-encoder reranker (`src/rerank.py`) — demoed on two cases
      (SEC-filing claim, fuzzier Wikipedia definitional claim) in
      `notebooks/phase3_evaluation.ipynb`
- [x] Extend `eval/compare_retrieval.py` with a `hybrid_rerank` row
      (hit_rate@3/MRR@3)
- [x] Wire `rerank()` into `verify_claim()` (`src/verifier.py`) — retrieves
      top-5 via `hybrid_search`, reranks to top-3, judges on the reranked
      set. Verified live (Apple revenue claim -> VERIFIED, correct
      source/quote).
- [x] Expand `data/eval_claims.csv` — see "Eval dataset expansion" below
- [~] RAGAS + LLM-as-judge evaluation, 2 prompts — see "RAGAS evaluation" below.
      Pipeline built and works; `VERDICT_PROMPT_V1` has real numbers,
      `VERDICT_PROMPT_V2` comparison incomplete (blocked by a free-tier daily
      quota, not a bug)
- [ ] Query rewriting (LLM rephrases the claim before retrieval)

## Eval dataset expansion

The original 52-claim set had almost no coverage for two of the four KB
sources: 0 claims against `fred` (5 docs, 3332 chunks), 1 claim against
`wikipedia` (29 docs, 1896 chunks) — `secedgar`/`worldbank` had 31/15. Hybrid
search scored 100% hit_rate / 1.000 MRR on that set — a ceiling that hid
whatever the reranker/query-rewriting actually contribute, not evidence they
don't matter.

Added 24 claims (`data/eval_claims.csv`, ids 53-76): 12 FRED (GDP, UNRATE,
FEDFUNDS, DGS10, CPIAUCSL — real values pulled from the DB, not invented),
12 Wikipedia (definitional claims from articles already indexed). Also added
a `fred` branch to `eval/compare_retrieval.py`'s `is_relevant()` — it had no
case for that source, so any FRED claim would've silently scored as a miss
regardless of retrieval quality.

Updated numbers, 68 non-INSUFFICIENT claims: `hybrid_rrf` hit_rate@5=93%
(63/68) MRR@5=0.873 → `hybrid_rerank` hit_rate@3=93% (63/68) MRR@3=0.919.
Reranking still improves ranking quality (MRR), no longer a ceiling.

The 5 remaining misses are all FRED claims, and they share one cause: a
**source collision**, not a vocabulary problem. "US GDP in the third quarter
of 2019..." retrieves World Bank's "GDP (current US\$) — United States"
instead of FRED's `GDP` series chunk — same concept, different source,
close enough lexically that hybrid search picks the wrong one. This is
concrete evidence for a next step, not a hypothetical: query rewriting (or
the source-type hint already noted as backlog in
[phase-2-rag-pipeline.md](phase-2-rag-pipeline.md)) has a real, measurable
problem to solve here.

## RAGAS evaluation

Hit_rate/MRR only measure retrieval. RAGAS adds LLM-as-judge scoring for
whether the judge's **verdict** actually follows from the evidence it saw:
**faithfulness** (does every part of the verdict trace back to the retrieved
chunks, or did the model add something from its own knowledge) and **context
precision** (was the retrieved evidence actually relevant, or noise).

`ragas==0.4.3`'s public API is `ragas.metrics.collections.{Faithfulness,
ContextPrecisionWithoutReference, ...}` — typed classes, not the
`from ragas.metrics import faithfulness` style shown in most tutorials (an
older version's interface; that top-level name isn't exported in this
version). LLM wiring is `ragas.llms.llm_factory(model, client=AsyncOpenAI(...))`
via the `instructor` library, separate from the `langchain_openai.ChatOpenAI`
client used everywhere else in this project — reuses the same
`base_url`/`api_key` from `src/config.py`'s `LLM_PROVIDERS`, just a different
client object.

**Dependency fix required:** `ragas==0.4.3` unconditionally imports
`langchain_community.chat_models.vertexai`, a module removed in
`langchain-community>=0.4` (moved to `langchain-google-vertexai`) — breaks
`import ragas` outright regardless of which LLM you actually use. Pinned
`langchain-community<0.4` in `pyproject.toml`.

**"2 prompts" rubric line:** `verifier.py` now has `VERDICT_PROMPT_V1`
(original) and `VERDICT_PROMPT_V2` (asks for step-by-step `reasoning` before
deciding — the `reasoning`-before-score pattern from the
[LLM Zoomcamp agent-evaluation lesson](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/04-evaluation/lessons/14-agent-evaluation.md)).
`Verdict.reasoning` is a required field either prompt uses.

`eval/ragas_eval.py` runs both prompts across a sample of `eval_claims.csv`,
scoring verdict accuracy (vs. `expected_verdict`) plus faithfulness/context
precision per claim, with per-claim try/except so one bad claim doesn't
crash the whole run (logs it and moves on instead).

**Results (sample of 10, seed=42), partial on two providers:**

| Prompt | Provider | Accuracy | Faithfulness | Context precision |
|---|---|---|---|---|
| `VERDICT_PROMPT_V1` | Groq `openai/gpt-oss-20b` | 90% (9/10) | 0.905 | 0.929 |
| `VERDICT_PROMPT_V1` | OpenRouter `poolside/laguna-xs-2.1:free` | 100% (5/5 before quota hit) | 0.792 | 1.000 |
| `VERDICT_PROMPT_V2` | both | incomplete (≤1/10 scored either run) | — | — |

**Real constraint, not a code bug — confirmed on two independent free tiers:**

- Groq caps `openai/gpt-oss-20b` at 8000 tokens/minute *and* 200,000
  tokens/day (TPD). Three LLM calls per claim (judge + faithfulness +
  context precision) meant V1's 10-claim run alone used 198,191/200,000 of
  the day's quota — V2, run right after, got blocked almost immediately.
- OpenRouter's free tier caps at 50 requests/day *per account*. A fresh
  account (new API key) hit the same wall mid-way through V1 — the reset
  timestamp OpenRouter returns is a fixed daily boundary, not a per-account
  clock, so "make a new account" buys a few extra requests, not a full
  reset.
- Both failures surfaced cleanly (skipped-and-logged per claim, not crashed
  or silently averaged) specifically because `eval/ragas_eval.py` wraps each
  claim's scoring in its own try/except.

Back-of-envelope: the full comparison needs 76 claims × 2 prompts × 3 LLM
calls ≈ 456 requests — past what either provider's free tier gives in a
day. This needs a paid tier (or spreading the run across several days) to
actually finish, not a code fix.

**Directionally, both partial runs agree:** high accuracy (90-100% on this
sample), high faithfulness (0.79-0.91), near-perfect context precision
(0.93-1.0) for `VERDICT_PROMPT_V1`. Not enough data to call a winner between
V1 and V2 — that's the real open item, not the pipeline itself.

[← Back to README](../README.md)
