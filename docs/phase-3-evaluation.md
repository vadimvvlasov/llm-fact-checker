# Phase 3 — Hybrid Search + Evaluation

**Status: in progress.** Reranker built and demoed
(`notebooks/phase3_evaluation.ipynb`); RAGAS eval and query rewriting still open.

## Goal

Make retrieval better, then measure how much better — hit-rate/MRR per
retrieval strategy, plus RAGAS + LLM-as-judge scores comparing baseline vs
hybrid vs hybrid+rerank.

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
- [ ] Wire `rerank()` into `verify_claim()` (`src/verifier.py`)
- [ ] Extend `eval/compare_retrieval.py` with a `hybrid_rerank` row
      (hit_rate@3/MRR@3)
- [ ] RAGAS + LLM-as-judge evaluation (baseline vs hybrid vs hybrid+rerank)
- [ ] Query rewriting (LLM rephrases the claim before retrieval)

[← Back to README](../README.md)
