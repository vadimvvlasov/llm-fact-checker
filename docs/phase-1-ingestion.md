# Phase 1 — Data + Ingestion

In this phase we build the knowledge base the whole fact-checker relies on:
four public data sources, pulled through `dlt` pipelines into Postgres,
then chunked and embedded into a `pgvector` store.

## Project overview

A knowledge-base ingestion pipeline that:

- Pulls financial/economic data from 4 public sources: Wikipedia, World Bank,
  FRED, SEC EDGAR
- Loads each source into its own raw staging schema with `dlt`
  (incremental, `merge` write disposition)
- Chunks and embeds the raw rows into a shared `documents` /
  `document_chunks` table
- Runs on Postgres + `pgvector`, with HNSW and full-text indexes already in
  place for the hybrid search we add in Phase 3

## Data sources

**Wikipedia** (MediaWiki API) — 29 articles on financial/economic terms
(GDP, Inflation, Unemployment, Stock market, Balance sheet, P/E ratio, IPO,
M&A, etc. — full list in `WIKI_TOPICS`, `fetch_wikipedia.py`). Pulls
`title`, `url`, `content` (plaintext extract). Definitional/contextual
base — explains terms, not numeric facts.

**World Bank** (`api.worldbank.org`) — 3 indicators × 8 countries (US, RU,
CN, DE, GB, BR, IN, JP): GDP (current US$), inflation (CPI annual %),
unemployment (% of labor force). Pulls `country`, `country_code`,
`indicator_code`, `indicator_label`, `year`, `value` as a yearly time
series. Macro facts for claims like "US GDP in 2025 was $X".

**FRED** (Federal Reserve Economic Data, `api.stlouisfed.org`, needs
`FRED_API_KEY`) — 5 series, US only, since 2015: GDP, CPI, unemployment
rate, fed funds rate, 10-year treasury rate. Pulls `series_id`,
`series_label`, `date`, `value` at higher frequency (monthly/daily) than
World Bank's yearly data — complements it with denser US macro history.

**SEC EDGAR** (XBRL Company Facts API, `sec.gov`) — 8 tickers (AAPL, MSFT,
AMZN, TSLA, GOOGL, META, JPM, WMT), 10-K annual filings only. Pulls
Revenue, Net income, Total assets per fiscal year: `ticker`,
`company_name`, `tag`, `fiscal_year_end`, `value_usd`, `form`, `filed`.
Corporate financial facts for claims like "Apple's revenue for FY2025 was
$X".

Wikipedia gives qualitative context/definitions; World Bank + FRED + SEC
EDGAR give quantitative, checkable facts (numbers, dates, amounts) — the
actual target for claim verification.

## Setting up the project

Start Postgres with the `pgvector` extension:

```bash
docker compose up -d postgres
```

`db/init.sql` runs automatically on first start and creates `documents`,
`document_chunks` (with an `hnsw` vector index and a generated
`tsvector` column for full-text search), plus the raw staging schemas
each `dlt` resource writes into.

Install dependencies:

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in `FRED_API_KEY` (free,
[register here](https://fred.stlouisfed.org/docs/api/api_key.html)).
The other three sources need no key.

## Fetching the data

Each source is a small `dlt` resource in `ingest/`. Run them independently —
they write to their own schema, so order doesn't matter:

```bash
uv run python -m ingest.fetch_wikipedia    # 29 financial/economic articles
uv run python -m ingest.fetch_worldbank    # GDP, inflation, unemployment × 8 countries
uv run python -m ingest.fetch_fred         # US macro series, needs FRED_API_KEY
uv run python -m ingest.fetch_secedgar     # 10-K revenue/income/assets × 8 tickers
```

Wikipedia is the one to look at closer — the `wikipedia` PyPI package no
longer works (Wikipedia now requires a `User-Agent`, the package doesn't
send one and gets a `403`). We call the MediaWiki API directly instead:

```python
resp = requests.get(
    "https://en.wikipedia.org/w/api.php",
    headers={"User-Agent": USER_AGENT},
    params={"action": "query", "prop": "extracts|info", "explaintext": 1,
            "titles": title, "format": "json"},
)
```

SEC EDGAR has the same requirement — a `User-Agent` with real contact info,
or every request gets rejected.

## Chunking and embedding

`build_vector_store.py` reads each raw staging table, turns rows into text,
embeds them, and writes to the shared vector store:

```bash
uv run python -m ingest.build_vector_store
```

Wikipedia articles go through sentence-level chunking:

```python
from src.chunking import chunk_text

chunks = chunk_text(article_content, sentences_per_chunk=4, overlap=1)
```

Structured sources (World Bank, FRED, SEC EDGAR) don't need chunking — each
row already is one fact, so we template it into a sentence instead:

```python
facts = [
    f"{company_name} ({ticker}) reported {tag} of ${value_usd:,.0f} "
    f"for fiscal year ending {fiscal_year_end}."
    for row in group_rows
]
```

Both paths go through the same embedding call:

```python
from src.embeddings import embed_texts

embeddings = embed_texts(chunks)  # sentence-transformers/all-MiniLM-L6-v2, 384-dim, local
```

## Result

```
uv run python -m ingest.build_vector_store
wikipedia: 29 articles -> 1896 chunks
worldbank: 24 series -> 1226 chunks
fred: 5 series -> 3332 chunks
secedgar: 24 series -> 392 chunks
TOTAL chunks in vector store: 6846
```

## What we learned

- **dlt variant columns silently hide bad data.** If a resource yields a
  field as `int` in some rows and `float` in others (World Bank: GDP as int,
  inflation as float), dlt creates a shadow variant column
  (`value__v_double`) and leaves the original `value` NULL for the
  mismatched rows. Caught it via `count(*) FILTER (WHERE value IS NULL)` —
  1156/1226 rows were NULL. Fix: cast numeric fields to `float(...)` before
  `yield`.
- **SEC EDGAR changes XBRL tags for revenue over time** (the ASC 606
  transition moved `Revenues` to
  `RevenueFromContractWithCustomerExcludingAssessedTax`). Taking only the
  first tag with data loses history — AAPL came back with 3 years instead
  of 10. Fix: merge both tags, dedupe by `end` date, keep the most recently
  `filed` value.
- 8 companies and 8 countries is a deliberate MVP scope for plausible demo
  claims, not a technical ceiling — extend by editing `TICKERS` /
  `WB_COUNTRIES`.

## Known issues (before Phase 2 automates this)

- ~~`build_vector_store.py` has no upsert and no unique constraint on
  `documents.title` — running it twice duplicates every document and
  chunk.~~ **Fixed 2026-07-07** — hit this for real (58/48/48 docs instead
  of 29/24/24, an exact ×2 from a stale `pgdata` volume plus a second run).
  `run()` now truncates `document_chunks`/`documents` before rebuilding, so
  it's a full-rebuild, not an append. Still no incremental upsert — fine for
  now since Phase 1 doesn't run on a schedule yet; revisit if Phase 2's
  Airflow DAG needs incremental loads instead of a full daily rebuild.
- No retry/backoff on the raw `requests` calls — a transient 429/5xx fails
  the whole run. Still open, low priority (all 4 sources were fetched
  clean today, no retries needed in practice).

We now have a populated, reproducible vector store. In Phase 2 we build the
claim extractor and the RAG chain on top of it.

[← Back to README](../README.md)
