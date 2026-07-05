# Fact-Checker RAG

RAG system that verifies claims in business reports against public financial/economic sources (LLM Zoomcamp capstone).

**Problem:** business reports contain factual errors and hallucinations (see the KPMG case) — manually checking every number against sources takes hours.

**Example:** `"Apple's revenue in FY2023 was $394B"` → cross-checked against SEC EDGAR 10-K → `VERIFIED` + source quote.

Takes report text → extracts claims → retrieves supporting evidence from a knowledge base (Wikipedia, World Bank, FRED, SEC EDGAR) → returns a verdict per claim: `VERIFIED` / `REFUTED` / `INSUFFICIENT` with source citation.

## Quick start

```bash
cp .env.example .env        # fill in FRED_API_KEY, OPENAI_API_KEY
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
