# Fact-Checker RAG

RAG system that checks claims in business reports against public financial and economic sources. LLM Zoomcamp capstone project.

**Problem.** Business reports contain factual errors and hallucinations. The KPMG case is one public example. Checking every number by hand takes hours.

**What it does:**
- Takes report text as input.
- Extracts factual claims from the text.
- Retrieves supporting evidence from a knowledge base built from 4 public sources: Wikipedia (definitions/context), World Bank, FRED, and SEC EDGAR (the actual checkable numbers).
- Returns a verdict per claim: `VERIFIED`, `REFUTED`, or `INSUFFICIENT`.
- Cites the exact source and quote behind each verdict.

**Example:** `"Apple's revenue in FY2023 was $394B"` → checked against SEC EDGAR 10-K → `VERIFIED` + source quote.

**Who it's for:** analysts, auditors, and researchers who verify quantitative claims in reports and don't want to check every number by hand.

**Demo:** see [Quick start](#quick-start) below. No report text handy? The app has a "Try an example" dropdown that fills in a known-good sample — more in [docs/manual-qa-reports.md](docs/manual-qa-reports.md).

<p align="center">
  <img src="docs/screenshots/ui-verdict-cards.jpg" alt="Streamlit UI showing verdict cards for two claims" width="100%"><br>
  <img src="docs/screenshots/monitoring-dashboard.jpg" alt="Monitoring dashboard verdict distribution chart" width="100%">
</p>

**Why this stack.** RAG + LLM-as-verifier over structured financial data is a pattern used in production fact-checking/audit tools today (e.g. [Hebbia](https://www.hebbia.com/)).

## Evaluation criteria — where to look

| Criterion | Status | Where |
|---|---|---|
| Problem description | ✅ | above |
| RAG flow (knowledge base + LLM) | ✅ | [Architecture](#architecture) |
| Retrieval evaluation | ✅ 8 methods compared, hybrid+rerank wins | [Architecture → evaluation](#architecture), [docs/phase-3-evaluation.md](docs/phase-3-evaluation.md) |
| LLM (judge) evaluation | ✅ 2 prompts compared | same |
| Interface | ✅ Streamlit UI + FastAPI API | [Architecture → fact-checking app](#architecture), [Quick start](#quick-start) |
| Ingestion pipeline | ✅ automated — dlt + Airflow DAG | [Architecture → ingestion](#architecture) |
| Monitoring | ✅ user feedback + 5-chart dashboard | [Architecture → fact-checking app](#architecture) |
| Containerization | ✅ full stack in docker-compose | [Quick start](#quick-start) |
| Reproducibility | ✅ one-command paths, dataset in repo | [Quick start](#quick-start) |
| Best practices (hybrid search, re-ranking, query rewriting) | ✅ all 3, all evaluated | [Best practices](#best-practices) |

## Architecture

Three independent processes share one Postgres database. **Knowledge-base ingestion** (Airflow, scheduled) writes the knowledge base; the **fact-checking app** (Streamlit, on demand) reads it to check claims; **evaluation** (offline, dev-time) reads it to measure retrieval and judge quality. Nothing runs the other two — the database is the only coupling.

```mermaid
flowchart TB
    ING["🔄 Knowledge-base ingestion — Airflow<br/>scheduled · writes"]
    VER["✅ Fact-checking app — Streamlit UI + monitoring<br/>on demand · reads"]
    EVAL["📊 Retrieval &amp; judge evaluation<br/>offline dev-time · reads"]
    DB[("Postgres + pgvector<br/>knowledge base + monitoring log")]

    ING -->|write chunks| DB
    DB -->|retrieve| VER
    DB -->|retrieve| EVAL
```

The three processes in detail:

**Knowledge-base ingestion** — builds the searchable knowledge base. Airflow DAG `dags/fact_checker_dag.py`, runs daily. Fetches 4 public APIs (Wikipedia, World Bank, FRED, SEC EDGAR), loads raw data into Postgres, splits long text into sentence chunks, turns numeric facts into short sentences, embeds every chunk.

```mermaid
flowchart TB
    subgraph FETCH["4 parallel Airflow tasks — dlt (merge, idempotent)"]
        WIKI["fetch_wikipedia"]
        WB["fetch_worldbank"]
        FRED["fetch_fred"]
        SEC["fetch_secedgar"]
    end
    FETCH --> RAW["Postgres raw tables<br/>(wikipedia_raw, worldbank_raw, fred_raw, secedgar_raw)"]
    RAW --> REBUILD["rebuild_vector_store<br/>(depends on all 4 — full rebuild each run)"]
    REBUILD --> CHUNK["chunk long text + numeric facts → sentences"]
    CHUNK --> EMB["embed (all-MiniLM-L6-v2)"]
    EMB --> KB[("document_chunks + pgvector index")]
```

Details: [docs/phase-1-ingestion.md](docs/phase-1-ingestion.md). Tutorial notebook: [notebooks/phase1_ingestion.ipynb](notebooks/phase1_ingestion.ipynb).

**Fact-checking app (interface + monitoring)** — the runtime that turns report text into verdicts. Streamlit `app.py`, on demand: claim input → verdict cards with source + quote, 👍/👎 feedback per run. A `POST /verify` API (`src/api.py`) exposes the same pipeline without the UI. Every run (claims, verdicts, tokens, response time) is logged to Postgres; a second Streamlit page (`pages/1_Monitoring.py`) charts it — verdict distribution, latency p95, feedback ratio, tokens/query, retrieval hit rate.

```mermaid
flowchart TB
    TXT["report text"] --> EX["extract_claims (LLM)"]
    EX --> HS["hybrid search — pgvector + full-text, RRF"]
    KB[("document_chunks")] -.->|retrieve| HS
    HS --> RR["cross-encoder rerank top-5"]
    RR --> JUDGE["LLM judge (VERDICT_PROMPT_V1)"]
    JUDGE --> V["verdict per claim — VERIFIED / REFUTED / INSUFFICIENT + source quote"]
    V --> LOG[("verification_runs + 👍/👎 feedback")]
    LOG --> DASH["monitoring dashboard (pages/1_Monitoring.py)"]
```

```
POST /verify  { "text": "Apple's revenue for fiscal year ending 2025-09-27 was $416,161,000,000." }

→ { "claims": [{ "claim": "...", "verdict": "VERIFIED",
      "source": "Apple Inc. (AAPL) — Revenue",
      "quote": "Apple Inc. (AAPL) reported Revenue of $416,161,000,000 for fiscal year ending 2025-09-27 (10-K filed 2025-10-31)." }] }
```

Details: [docs/phase-2-rag-pipeline.md](docs/phase-2-rag-pipeline.md) (RAG flow), [docs/phase-4-ui-monitoring.md](docs/phase-4-ui-monitoring.md) (UI + monitoring). Walkthrough notebook: [notebooks/phase2_rag_pipeline.ipynb](notebooks/phase2_rag_pipeline.ipynb).

**Retrieval & judge evaluation** — offline measurement, not part of the runtime. Scores retrieval and judge variants against a labeled set (`data/eval_claims.csv`), so the winners above are measured, not assumed:
- Compared 8 retrieval methods on a 68-claim labeled set. Hybrid search + reranking wins: 90% hit_rate, 0.890 MRR.
- Compared 2 judge prompts on the full 76-claim set. The simpler prompt wins: 79% accuracy vs. 74%.
- Tested query rewriting on 4 local LLMs. Found a real pattern: the model with the best retrieval score gave the worst final answers, and vice versa — retrieval quality and answer quality are not the same thing. See the doc for why.

```mermaid
flowchart TB
    SET["data/eval_claims.csv — 76 labeled claims"] --> RUN["run retrieval + judge variants"]
    KB[("document_chunks")] -.->|retrieve| RUN
    RUN --> M["metrics — hit_rate@5 · MRR · RAGAS (faithfulness, context precision) · accuracy"]
```

**Backlog:** `document_chunks.metadata` has a GIN index (`db/init.sql`) but no query filters on it yet — source-filtered hybrid search could cut retrieval noise further. See "Further research" in the doc.

Details: [docs/phase-3-evaluation.md](docs/phase-3-evaluation.md). Tutorial notebook: [notebooks/phase3_evaluation.ipynb](notebooks/phase3_evaluation.ipynb).

## Best practices

Per the [course rubric](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md#evaluation-criteria):
- [x] Hybrid search (text + vector, fused with RRF) — implemented and evaluated.
- [x] Document re-ranking (cross-encoder) — implemented and evaluated.
- [x] Query rewriting — implemented and evaluated across 4 models. Result: it helps retrieval, but not always the final answer. See [docs/phase-3-evaluation.md](docs/phase-3-evaluation.md).

## Tech stack

100% tools covered in the LLM Zoomcamp course.

| Layer | Tool | Why |
|---|---|---|
| Ingestion | [dlt](https://dlthub.com/) | incremental loads (`merge` write disposition) into per-source raw schemas |
| HTTP | `requests` (shared `ingest/http.py` helper) | no framework needed for 4 simple REST/JSON APIs |
| Storage | Postgres 16 + [pgvector](https://github.com/pgvector/pgvector) | one database for raw staging tables and the vector store — no separate vector DB |
| Embeddings | [sentence-transformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`, 384-dim) | local, free, no API cost — good enough for MVP-scale retrieval |
| Retrieval | pgvector HNSW + Postgres full-text (`tsvector`), fused with RRF, cross-encoder rerank, LLM query rewriting | `src/db.py`, `src/rerank.py`, `src/query_rewrite.py` — all evaluated, see [Architecture → evaluation](#architecture) |
| RAG chain | LangChain | claim extraction (`src/claim_extractor.py`) + verifier (`src/verifier.py`), via OpenRouter free tier (model in `src/config.py`) — $0 LLM cost |
| Orchestration | Airflow (`dags/fact_checker_dag.py`) | separate `airflow` service (`Dockerfile.airflow`), scheduled daily ingestion so the KB doesn't go stale |
| Evaluation | RAGAS + LLM-as-judge | hit_rate/MRR per retrieval method, accuracy/faithfulness/context precision per prompt — `eval/compare_retrieval.py`, `eval/ragas_eval.py` |
| Monitoring | Postgres run/feedback log + dashboard (`src/monitoring.py`, `pages/1_Monitoring.py`) | verdict distribution, latency p95, feedback ratio, tokens/query, retrieval hit rate |
| UI | Streamlit (`app.py` + `pages/`) | claim input → verdict cards with sources, monitoring dashboard in sidebar |
| API | FastAPI + uvicorn | `src/api.py` — `/health` + `POST /verify` (claim extraction + verdict) |
| Package/env | [uv](https://docs.astral.sh/uv/) | fast installs, single lockfile |
| Testing | pytest | `tests/` |
| Infra | Docker Compose | one command to bring up Postgres+pgvector |

## Quick start

Both paths need API keys first: `cp .env.example .env`, then fill in
`FRED_API_KEY` ([free](https://fred.stlouisfed.org/docs/api/api_key.html)) and
`OPENROUTER_API_KEY` ([free](https://openrouter.ai/settings/keys)). Every
component reads the same `.env`.

### Option A — Docker (one clean path, recommended for reviewers)

```bash
docker compose up -d postgres                    # DB first (has a healthcheck)

# Populate the knowledge base once (empty until this runs — the app returns
# INSUFFICIENT for everything otherwise). Runs inside the app image:
docker compose run --rm app uv run python -m ingest.fetch_wikipedia
docker compose run --rm app uv run python -m ingest.fetch_worldbank
docker compose run --rm app uv run python -m ingest.fetch_fred
docker compose run --rm app uv run python -m ingest.fetch_secedgar
docker compose run --rm app uv run python -m ingest.build_vector_store

docker compose up -d app ui                      # API → :8000, UI → :8501
```

Open http://localhost:8501 for the Streamlit app (monitoring dashboard in the
sidebar). The `app` service serves `POST /verify` at http://localhost:8000.

### Option B — Local (uv)

```bash
docker compose up -d postgres        # just the DB in Docker
uv sync
uv run python -m ingest.fetch_wikipedia
uv run python -m ingest.fetch_worldbank
uv run python -m ingest.fetch_fred
uv run python -m ingest.fetch_secedgar
uv run python -m ingest.build_vector_store
```

Then start the API and UI **in two separate terminals** (each blocks its shell):

```bash
uv run uvicorn src.api:app --reload     # terminal 1 → API at :8000
uv run streamlit run app.py             # terminal 2 → UI at :8501
```

### Reproduce the evaluation

Needs a populated knowledge base (ingestion above) + `data/eval_claims.csv` (in the repo):

```bash
uv run python eval/compare_retrieval.py   # hit_rate@5 / MRR per retrieval method
uv run python eval/ragas_eval.py          # accuracy + RAGAS faithfulness / context precision per judge prompt
```

### Tests

```bash
uv run pytest
```

### Scheduled ingestion (optional)

To re-run ingestion on a schedule instead of manually:

```bash
docker compose up -d airflow   # builds Dockerfile.airflow on first run
```

Open http://localhost:8080 (login from `AIRFLOW_ADMIN_*` in `.env`) and unpause `fact_checker_daily_ingestion`, or trigger it from the CLI:

```bash
docker exec fact-checker-airflow airflow dags list                              # confirm it loaded
docker exec fact-checker-airflow airflow dags unpause fact_checker_daily_ingestion
docker exec fact-checker-airflow airflow dags trigger fact_checker_daily_ingestion
```

The DAG re-runs the 4 `ingest.fetch_*` steps + `ingest.build_vector_store` daily — the same steps as the manual ingestion above, just scheduled.

## Further reading

Per-component deep dives (design decisions, full numbers, further research) linked inline in [Architecture](#architecture) above. Also see:

- [Manual QA report examples](docs/manual-qa-reports.md) — 27 paste-in test blocks for the Streamlit app
