# Phase 4 — UI + Monitoring

**Status: done.** Streamlit UI + Postgres-backed monitoring dashboard, following
the LLM Zoomcamp course's own [05-monitoring](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/05-monitoring)
module pattern.

## What it does

`app.py` — the main page:

1. Text area for report text.
2. `extract_claims()` + `verify_claim()` per claim (Phase 2/3 pipeline, unchanged).
3. One card per claim: verdict icon, claim text, source, quote.
4. Every run is logged to Postgres (`src/monitoring.py`): claims checked, verdicts,
   token usage, response time.
5. 👍/👎 buttons store feedback against that run.

`pages/1_Monitoring.py` — a second page (native Streamlit multipage app, same
process/port, switchable from the sidebar):

1. **Verdict distribution** — count of VERIFIED/REFUTED/INSUFFICIENT across all
   logged claims.
2. **Latency** — p95 and median response time, trend over runs.
3. **Feedback ratio** — 👍 vs 👎 count and percentage.
4. **Tokens per query** — avg tokens/run and tokens/claim. Used instead of a
   dollar cost figure: the LLM provider is OpenRouter's free tier
   (`src/config.py`), so actual cost is $0 — tokens are the honest signal.
5. **Retrieval hit rate** — share of claims that got a non-INSUFFICIENT verdict,
   i.e. retrieval surfaced evidence the judge could act on. A live-traffic
   complement to the offline hit_rate/MRR numbers in
   [phase-3-evaluation.md](phase-3-evaluation.md), which are measured against
   the labeled `data/eval_claims.csv` set, not production queries.

## Why Postgres instead of Langfuse

The original plan called for Langfuse. Implemented here as a Postgres run/feedback
log instead — same course-taught pattern as `05-monitoring/code/db_init.py` /
`db_save.py` / `db_feedback.py`, reusing this project's own `src/db.py`
connection helper rather than a second one. This gets every rubric-relevant
metric (verdict distribution, latency, feedback, cost proxy, hit rate) without
adding an external SaaS dependency for a capstone submission. Swapping in
Langfuse later would only mean changing `src/monitoring.py`'s implementation —
`app.py` and the dashboard page's charts wouldn't need to move.

## Schema

```sql
verification_runs (id, report_text, num_claims, input_tokens, output_tokens,
                    total_tokens, response_time_s, created_at)
claim_verdicts    (id, run_id -> verification_runs, claim, verdict, source, quote)
run_feedback      (id, run_id -> verification_runs, score, created_at)
```

Created by `src/monitoring.py:ensure_schema()` (`CREATE TABLE IF NOT EXISTS`,
called on every app start) — not in `db/init.sql`, since that only runs on a
fresh Postgres volume and would require dropping the Phase 1-3 ingested data
to pick up new tables.

## Running it

```bash
uv run streamlit run app.py     # http://localhost:8501, dashboard in sidebar
# or
docker compose up -d ui         # same, containerized
```

## Verified

End-to-end smoke test against the real dev Postgres + OpenRouter LLM: claim
extracted, verdict VERIFIED with source, run + feedback rows written, both
Streamlit pages return HTTP 200 with no server-side exceptions. Test rows were
deleted afterward so they don't skew the dashboard's real numbers.
