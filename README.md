# Fact-Checker RAG

RAG system that verifies claims in business reports against public financial/economic sources (LLM Zoomcamp capstone).

**Problem:** business reports contain factual errors and hallucinations (see the KPMG case) — manually checking every number against sources takes hours.

**Example:** `"Apple's revenue in FY2023 was $394B"` → cross-checked against SEC EDGAR 10-K → `VERIFIED` + source quote.

Takes report text → extracts claims → retrieves supporting evidence from a knowledge base (Wikipedia, World Bank, FRED, SEC EDGAR) → returns a verdict per claim: `VERIFIED` / `REFUTED` / `INSUFFICIENT` with source citation.

**Who it's for:** analysts, auditors, and researchers who need to verify quantitative claims in reports without manually cross-checking every number against a source.

**Input:** raw report text (paragraph or full document).

**Output:** list of extracted claims, each with a verdict (`VERIFIED` / `REFUTED` / `INSUFFICIENT`), the matched source, and a direct quote.

**Evaluation:** in progress (Phase 3) — RAGAS + LLM-as-judge against a 76-claim labeled test set (`data/eval_claims.csv`). Numbers land here once the phase ships.

**Demo:** in progress (Phase 4) — Streamlit UI link lands here once deployed.

**Why this stack:** RAG + LLM-as-verifier over structured financial/public data sources is the same core pattern used in production by [Hebbia](https://www.hebbia.com/) (financial due-diligence RAG, 40%+ of large asset managers by AUM), [AuditBoard](https://venturebeat.com/ai/auditboard-upgrades-its-risk-management-platform-with-built-in-llm-descriptions) (LLM-assisted risk/control workflows for internal audit), and Thomson Reuters' Westlaw AI (legal fact-verification — a [Stanford study](https://www.buildmvpfast.com/blog/ai-legal-research-westlaw-lexis-casetext-llms-2026) found it hallucinates 33% of the time, which is exactly the failure mode this project targets).

## Architecture

The system is built in 5 phases. Each phase is a separate, independently runnable stage of the RAG pipeline.

### Phase 1 — Data + Ingestion ✅ done

Builds the knowledge base. The foundation for every later phase.

- **Input:** 4 public APIs — Wikipedia, World Bank, FRED, SEC EDGAR.
- **What it does:** fetches each source. Loads raw data into Postgres. Splits long articles into sentence chunks. Turns numeric facts into short sentences. Embeds every chunk into a vector.
- **Output:** a searchable knowledge base — `documents` and `document_chunks` tables in Postgres.

Details: [Phase 1 — Ingestion](docs/phase-1-ingestion.md). Step-by-step tutorial: [notebooks/phase1_ingestion.ipynb](notebooks/phase1_ingestion.ipynb).

### Phase 2 — RAG Pipeline + Orchestration 🚧 in progress

Turns report text into verified claims, and keeps the knowledge base fresh on a schedule.

- **Input:** raw report text + the Phase 1 knowledge base.
- **What it does:** an LLM (LangChain) extracts factual claims from the text. A vector-search RAG chain retrieves supporting evidence per claim. An Airflow DAG re-runs ingestion daily so the knowledge base doesn't go stale.
- **Output:** `POST /verify` endpoint → a verdict per claim — `VERIFIED` / `REFUTED` / `INSUFFICIENT`, with the matched source quote.

Details: [Phase 2 — RAG Pipeline + Orchestration](docs/phase-2-rag-pipeline.md) (in progress — claim extractor + verdict logic + `POST /verify` done, Airflow DAG not started). Walkthrough: [notebooks/phase2_rag_pipeline.ipynb](notebooks/phase2_rag_pipeline.ipynb).

### Phase 3 — Hybrid Search + Evaluation 🚧 in progress

Makes retrieval better, then measures how much better.

- **Input:** the Phase 2 chain + a labeled test set (`data/eval_claims.csv`, 76 claims).
- **What it does:** combines pgvector + Postgres full-text search via RRF (`src/db.py`: `text_search`, `vector_search`, `hybrid_search`), reranks top-5 with a cross-encoder, rewrites the claim before searching. RAGAS + LLM-as-judge score the pipeline: baseline vs hybrid vs hybrid+rerank.
- **Output:** retrieval hit-rate/MRR per strategy, RAGAS faithfulness/accuracy numbers. `eval/compare_retrieval.py` already benchmarks minsearch vs pg full-text vs pgvector vs hybrid RRF on hit_rate@5/MRR@5 — reranker and RAGAS scoring still open.

**Backlog:** `document_chunks.metadata` has a GIN index (`db/init.sql`) but no query filters on it yet — source-filtered hybrid search (e.g. restrict to `secedgar` when the claim extractor tags a claim as company-financial) could cut retrieval noise. Blocked on Phase 2's claim extractor producing a source tag to filter on. Also untried: `hnsw.ef_search` tuning as a speed/accuracy knob in the eval harness.

Details: TODO — `docs/phase-3-evaluation.md` (not written yet).

### Phase 4 — UI + Monitoring ⏳ not started

Makes the project usable and observable by someone who isn't reading code.

- **Input:** the working Phase 2/3 pipeline.
- **What it does:** wraps it in a Streamlit UI (claim input → verdict cards with sources). Logs every query to Langfuse with a 👍/👎 feedback button.
- **Output:** a live demo, plus a Langfuse dashboard (verdict distribution, latency p95, feedback ratio, cost/query, retrieval hit rate).

Details: TODO — `docs/phase-4-ui-monitoring.md` (not written yet).

### Phase 5 — Polish + Submit ⏳ not started

Wraps the project up for review.

- **Input:** the finished Phase 1-4 system.
- **What it does:** writes the final README (architecture diagram, setup, examples), records a demo video, smoke-tests `docker compose up` on a clean clone.
- **Output:** submitted capstone project.

## Tech stack

100% tools covered in the LLM Zoomcamp course.

| Layer | Tool | Why |
|---|---|---|
| Ingestion | [dlt](https://dlthub.com/) | incremental loads (`merge` write disposition) into per-source raw schemas |
| HTTP | `requests` (shared `ingest/http.py` helper) | no framework needed for 4 simple REST/JSON APIs |
| Storage | Postgres 16 + [pgvector](https://github.com/pgvector/pgvector) | one database for raw staging tables and the vector store — no separate vector DB |
| Embeddings | [sentence-transformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`, 384-dim) | local, free, no API cost — good enough for MVP-scale retrieval |
| Retrieval | pgvector HNSW + Postgres full-text (`tsvector`), fused with RRF | implemented in `src/db.py`, benchmarked in `eval/compare_retrieval.py`; reranker still open (Phase 3) |
| RAG chain | LangChain (planned, Phase 2) | claim extraction + retrieval chain, via OpenRouter (`tencent/hy3:free`) — $0 LLM cost |
| Orchestration | Airflow (planned, Phase 2) | scheduled daily ingestion so the KB doesn't go stale |
| Evaluation | RAGAS + LLM-as-judge (planned, Phase 3) | baseline vs hybrid vs hybrid+rerank comparison — hit_rate/MRR harness already in `eval/compare_retrieval.py`, RAGAS not wired yet |
| Monitoring | Langfuse (planned, Phase 4) | latency/cost/feedback dashboards |
| UI | Streamlit (planned, Phase 4) | claim input → verdict cards |
| API | FastAPI + uvicorn | `src/api.py` — `/health` + `POST /verify` (claim extraction + verdict) |
| Package/env | [uv](https://docs.astral.sh/uv/) | fast installs, single lockfile |
| Testing | pytest | `tests/` |
| Infra | Docker Compose | one command to bring up Postgres+pgvector |

## Quick start

```bash
cp .env.example .env        # fill in FRED_API_KEY, OPENROUTER_API_KEY
docker compose up -d        # postgres+pgvector
uv sync
uv run python -m ingest.fetch_wikipedia
uv run python -m ingest.fetch_worldbank
uv run python -m ingest.fetch_fred        # needs FRED_API_KEY
uv run python -m ingest.fetch_secedgar
uv run python -m ingest.build_vector_store
uv run uvicorn src.api:app --reload
```

## Docs

- [Phase 1 — Ingestion](docs/phase-1-ingestion.md)
- [Phase 1 tutorial notebook](notebooks/phase1_ingestion.ipynb)
- [Phase 2 — RAG Pipeline + Orchestration](docs/phase-2-rag-pipeline.md)
- [Phase 2 walkthrough notebook](notebooks/phase2_rag_pipeline.ipynb)
