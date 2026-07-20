# Phase 1 — Data + Ingestion

Builds the knowledge base: 4 public sources → `dlt` → Postgres → chunked and
embedded into a `pgvector` store.

## Data sources

- **Wikipedia** (MediaWiki API) — 29 financial/economic term articles (GDP,
  inflation, balance sheet, P/E ratio, etc.). Definitional context, not numbers.
- **World Bank** (`api.worldbank.org`) — GDP, inflation, unemployment × 8
  countries, yearly.
- **FRED** (`api.stlouisfed.org`, needs `FRED_API_KEY`) — 5 US macro series
  (GDP, CPI, unemployment, fed funds rate, 10Y treasury), monthly/daily.
- **SEC EDGAR** (XBRL Company Facts API) — Revenue / Net income / Total
  assets from 10-K filings, 8 tickers.

Wikipedia supplies definitional context; World Bank, FRED, and SEC EDGAR
supply the checkable numbers claims get verified against.

## Setup

```bash
docker compose up -d postgres   # db/init.sql creates documents/document_chunks (hnsw + tsvector)
uv sync
cp .env.example .env            # fill in FRED_API_KEY (free)
```

## Fetch + build

```bash
uv run python -m ingest.fetch_wikipedia
uv run python -m ingest.fetch_worldbank
uv run python -m ingest.fetch_fred         # needs FRED_API_KEY
uv run python -m ingest.fetch_secedgar
uv run python -m ingest.build_vector_store
```

Each source is an independent `dlt` resource (own raw schema, `merge` write
disposition — order doesn't matter). `build_vector_store.py` chunks Wikipedia
articles (`src/chunking.py`, sentence-level) and templates the structured
sources into one-fact sentences, then embeds everything with
`sentence-transformers/all-MiniLM-L6-v2` (384-dim, local, no API cost).

**Note:** Wikipedia and SEC EDGAR both require a real `User-Agent` header —
the `wikipedia` PyPI package doesn't send one and gets `403`, so both sources
are called directly via `requests` (`ingest/http.py`) instead.

## Result

```
wikipedia: 29 articles -> 1896 chunks
worldbank: 24 series -> 1226 chunks
fred: 5 series -> 3332 chunks
secedgar: 24 series -> 392 chunks
TOTAL chunks in vector store: 6846
```

[← Back to README](../README.md)
