# Phase 2 — RAG Pipeline + Orchestration

**Status: done.** Turns report text into verified claims and keeps the
knowledge base fresh on a schedule.

- **Input:** raw report text + the Phase 1 knowledge base (6846 chunks).
- **Output:** `POST /verify` → a list of claims, each with a verdict
  (`VERIFIED` / `REFUTED` / `INSUFFICIENT`), the matched source, and a quote.

## 1. Claim extraction

An LLM (LangChain, structured output) pulls checkable claims — numbers/dates
tied to an entity, e.g. "Apple's revenue for FY2025 was $416.161B" — out of
report text (`src/claim_extractor.py`). Provider is configurable via
`LLM_PROVIDER` (`src/config.py`): `openrouter` (default, free tier, $0 cost),
`groq`, or `ollama` (local, no API key — CPU fallback for offline dev).

## 2. RAG chain (retrieval → verdict)

`src/verifier.py`'s `verify_claim()` runs `hybrid_search` (pgvector +
Postgres full-text, fused with RRF — `src/db.py`) per claim, then an LLM
judge (`VERDICT_PROMPT_V1`) returns a verdict + source + quote via structured
output. `INSUFFICIENT` is an explicit judge decision, not inferred from empty
results — retrieval always returns top-k, even when nothing relevant exists.

## 3. API — `POST /verify`

```
POST /verify
{ "text": "<report text>" }

→ 200
{ "claims": [
    { "claim": "Apple reported revenue of $416,161,000,000 for fiscal year ending 2025-09-27.",
      "verdict": "VERIFIED", "source": "Apple Inc. (AAPL) — Revenue",
      "quote": "Apple Inc. (AAPL) reported Revenue of $416,161,000,000 for fiscal year ending 2025-09-27 (10-K filed 2025-10-31)." }
  ]
}
```

## 4. Orchestration — Airflow DAG

![Airflow DAG graph](image.png)

`dags/fact_checker_dag.py` re-runs Phase 1 ingestion daily so the knowledge
base doesn't go stale: 4 independent `fetch_*` tasks → `rebuild_vector_store`
(full rebuild each run — no incremental upsert yet). Runs as a separate
`airflow` service (`Dockerfile.airflow`, `standalone` mode — single
container, SQLite metadata DB; fine for a capstone, not production HA).

[← Back to README](../README.md)
