# Phase 3 — Hybrid Search + Evaluation

**Status: done, mixed result on query rewriting.** Reranker, RAGAS (both
prompts, full 76-claim set), and query rewriting are all built and
evaluated. V1 vs V2 is resolved (V1 wins). Query rewriting is implemented
and evaluated, but the numbers don't show a clear win — see "Query
rewriting" below before treating it as a finished success.

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
- [x] RAGAS + LLM-as-judge evaluation, 2 prompts — see "RAGAS evaluation"
      below. Full 76-claim set, both prompts, run locally
      (`granite4.1:3b` via Ollama, no quota ceiling). `VERDICT_PROMPT_V1`
      wins; it's already `verifier.py`'s default.
- [x] Query rewriting (`src/query_rewrite.py`, LLM rephrases the claim
      before retrieval) — implemented, wired into `verify_claim()`,
      evaluated in `notebooks/phase3_evaluation.ipynb`. Result: hit_rate
      unchanged, MRR worse, one targeted collision case still resolves to
      the wrong source. See "Query rewriting" below.

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
close enough lexically that hybrid search picks the wrong one. Query
rewriting targets exactly this — see "Query rewriting" below for whether it
actually fixes it (short answer: not cleanly).

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

`eval/ragas_eval.py` runs both prompts across `eval_claims.csv`, scoring
verdict accuracy (vs. `expected_verdict`) plus faithfulness/context
precision per claim, with per-claim try/except so one bad claim doesn't
crash the whole run (logs it and moves on instead).

**Results, full 76-claim set, both prompts, run locally
(`granite4.1:3b` via Ollama — no free-tier quota, no sampling needed):**

| Prompt | Accuracy | Faithfulness* | Context precision |
|---|---|---|---|
| `VERDICT_PROMPT_V1` | **79% (60/76)** | 0.748 | **0.669** |
| `VERDICT_PROMPT_V2` | 74% (56/76) | 0.747 | 0.587 |

*Recomputed after fixing an aggregation bug found while reading these
results: RAGAS's `Faithfulness` metric returns `NaN` (not `None`) for a
verdict with no extractable factual statement — mostly `INSUFFICIENT`
verdicts — and `eval/ragas_eval.py`'s original averaging summed `NaN`
straight in, silently turning the *whole* average into `NaN` instead of
dropping just those claims. Fixed to drop `NaN` the same way it already
dropped `None` (3 claims dropped for V1, 10 for V2 — V2 producing more
`INSUFFICIENT` verdicts is also most of why its accuracy is lower).

**V1 wins** — higher accuracy, higher context precision, tied on
faithfulness. `verifier.py`'s default (`VERDICT_PROMPT_V1`) is already the
right call; no code change needed. Full transcript and per-claim breakdown:
`notebooks/phase3_evaluation.ipynb`, Stage 3.

## Query rewriting

`src/query_rewrite.py`: an LLM rewrites the claim into a search query before
retrieval, naming which of the four source types (Wikipedia / World Bank /
FRED / SEC EDGAR) the claim most plausibly belongs to when ambiguous — aimed
directly at the FRED-vs-World-Bank source collision documented above.
Wired into `verify_claim()` by default.

**Evaluated (`notebooks/phase3_evaluation.ipynb`, Stage 1), on the same
68-claim set, locally (`granite4.1:3b`):**

| Method | hit_rate | MRR |
|---|---|---|
| `hybrid_rrf` (no rewrite) | 93% (63/68) | 0.873 |
| `hybrid_rewrite` | 93% (63/68) | **0.765** |
| `hybrid_rerank` (no rewrite) | 93% (63/68) | 0.919 |
| `hybrid_rerank_rewrite` | 93% (63/68) | **0.909** |

**Not a clean win.** Hit_rate is exactly flat — rewriting didn't add a
single new hit — and MRR is worse in both variants: ranking quality dropped
even though hybrid_rrf/hybrid_rerank numbers were measured at 6846 chunks
vs. 6850 live now, a drift too small to explain a same-direction regression
on both metrics.

A single targeted check on the exact collision case ("US GDP in the third
quarter of 2019...") confirms why: rewriting does get FRED's chunk into the
candidate set (fixes *recall*), but the cross-encoder reranker still ranked
World Bank's chunk above it, and `verify_claim()` cited World Bank — wrong
source, even though the verdict itself (`VERIFIED`) was still correct.
Rewriting fixes recall, not ranking, and ranking is what the final citation
depends on.

**Open question, not resolved here:** whether query rewriting should stay
`verify_claim()`'s silent default given no measured retrieval benefit. It's
implemented and evaluated either way (satisfies the rubric's Best Practices
checklist item), but a systematic Stage 2 check (5 known-miss claims,
with/without rewriting) hasn't actually run yet — the notebook's
placeholder claim-id list was never filled in with real ids, so that check
found 0 matching claims and produced no signal. That's the next concrete
step before deciding either way.

[← Back to README](../README.md)
