# Phase 2 — RAG Pipeline + Orchestration

**Status: not started.** This doc is the plan, written before any Phase 2 code
exists, so implementation can follow it instead of improvising. Update this
file as design decisions land or change — don't let it go stale like the
Phase 1 doc almost did.

## Goal

Turn raw report text into a list of verified claims, and keep the Phase 1
knowledge base from going stale.

- **Input:** raw report text (paragraph or full document) + the Phase 1
  knowledge base (`documents` / `document_chunks`, 6846 chunks).
- **Output:** `POST /verify` → a list of claims, each with a verdict
  (`VERIFIED` / `REFUTED` / `INSUFFICIENT`), the matched source, and a direct
  quote.

Two independent pieces: the verify pipeline (claim extraction → retrieval →
verdict) and the ingestion scheduler (Airflow DAG). They don't depend on each
other and can be built in either order.

## 1. Claim extraction

An LLM reads the report text and pulls out checkable factual claims —
numbers, dates, amounts tied to a specific entity ("Apple's revenue for
FY2025 was $416.161B"), not opinions or forward-looking statements.

Open design decisions:

- **Model:** OpenRouter, not OpenAI directly — `OPENROUTER_API_KEY` +
  `LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free` in `.env.example`
  (same pattern as `llm-zoomcamp-hw2`: OpenAI-compatible client,
  `base_url="https://openrouter.ai/api/v1"`). Free-tier model, $0 cost —
  fits a capstone with no LLM budget. `langchain-openai`'s `ChatOpenAI`
  takes `openai_api_base`/`openai_api_key` so it works unchanged against
  OpenRouter. `langchain` + `langchain-openai` need adding to
  `pyproject.toml` (not there yet).
- **Output schema:** structured output (function calling / `with_structured_output`)
  so extraction returns a typed list, not text to re-parse — e.g.
  `[{claim: str, entity: str, metric: str, value: float, date: str}]`.
- **Source-type hint:** would help Phase 3's backlogged source-filtered
  retrieval (see README) if extraction also guesses which source a claim
  belongs to (`secedgar` / `worldbank` / `fred` / `wikipedia`). Nice-to-have,
  not required for a first working `/verify`.

## 2. RAG chain (retrieval → verdict)

Retrieval already exists — nothing new to build there. `src/db.py` has
`text_search`, `vector_search`, `hybrid_search` (RRF), all benchmarked in
`eval/compare_retrieval.py`. The chain just calls one of these per claim
(`hybrid_search` is the current best guess — no eval numbers yet to confirm
it beats plain vector search).

What's actually new for Phase 2:

- **Verdict logic:** given a claim + top-k retrieved chunks, decide
  `VERIFIED` / `REFUTED` / `INSUFFICIENT`. Two options:
  - LLM-as-judge: pass claim + chunks to an LLM, ask for a verdict + which
    chunk supports it. Simple, but is itself a judgment call worth
    evaluating in Phase 3 (this *is* the RAGAS/LLM-as-judge evaluation
    target).
  - Rule-based for numeric claims: parse the number out of the claim and
    the retrieved fact-sentence, compare with a tolerance (the eval set's
    `REFUTED` rows use gross mismatches — Apple's revenue off by $166B —
    so a tolerance-based check might get most of the way without an LLM
    call per claim). Wikipedia-sourced definitional claims would still need
    the LLM path.
  - Probably start with LLM-as-judge for everything — simplest to implement,
    matches what Phase 3 evaluates anyway. Revisit if latency/cost becomes a
    problem.
- **`INSUFFICIENT` handling:** `data/eval_claims.csv` already has rows with
  `expected_verdict=INSUFFICIENT` — claims with no matching doc in the KB
  (see `eval/compare_retrieval.py`'s `load_claims()`, which excludes them from
  hit-rate scoring since there's no correct retrieval target). The verdict
  logic needs a real "no good match" path, not just whatever the top-k
  returns.
- **Source quote:** return the actual retrieved chunk text as the citation,
  not a paraphrase.

## 3. API — `POST /verify`

Replace the `/health`-only stub in `src/api.py`.

```
POST /verify
{ "text": "<report text>" }

→ 200
{ "claims": [
    { "claim": "...", "verdict": "VERIFIED", "source": "secedgar:AAPL:Revenue",
      "quote": "Apple (AAPL) reported Revenue of $416,161,000,000 for fiscal year ending 2025-09-27..." },
    ...
  ]
}
```

Exact schema is a draft — firm it up once claim extraction's output shape is
settled (§1).

## 4. Orchestration — Airflow DAG

Re-runs Phase 1 ingestion on a schedule so the KB doesn't go stale.

- DAG re-runs the same 4 `ingest.fetch_*` modules + `ingest.build_vector_store`,
  daily.
- `build_vector_store.run()` already does a full truncate-and-rebuild (fixed
  2026-07-07, see [Phase 1 doc](phase-1-ingestion.md)) — safe to schedule as
  a full rebuild. No incremental upsert exists; revisit only if the daily
  full-rebuild cost becomes a problem in practice.
- Airflow itself isn't in `pyproject.toml`/`docker-compose.yml` yet — needs
  its own service (webserver + scheduler) added to compose.

## Task breakdown

- [ ] Add `langchain`, `langchain-openai`, `apache-airflow` to `pyproject.toml`
- [ ] Claim extractor module (`src/` or new `pipeline/`) with structured output
- [ ] Verdict logic (LLM-as-judge first pass) wired to `hybrid_search`
- [ ] `POST /verify` in `src/api.py`
- [ ] Airflow service in `docker-compose.yml` + DAG file
- [ ] Manual smoke test against a few `data/eval_claims.csv` rows before
      Phase 3 runs the full RAGAS evaluation

[← Back to README](../README.md)
