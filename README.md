# Fact-Checker RAG

RAG system that verifies claims in business reports against public financial/economic sources (LLM Zoomcamp capstone).

**Problem:** business reports contain factual errors and hallucinations (see the KPMG case) — manually checking every number against sources takes hours.

**Example:** `"Apple's revenue in FY2023 was $394B"` → cross-checked against SEC EDGAR 10-K → `VERIFIED` + source quote.

Takes report text → extracts claims → retrieves supporting evidence from a knowledge base (Wikipedia, World Bank, FRED, SEC EDGAR) → returns a verdict per claim: `VERIFIED` / `REFUTED` / `INSUFFICIENT` with source citation.

**Who it's for:** analysts, auditors, and researchers who need to verify quantitative claims in reports without manually cross-checking every number against a source.

**Input:** raw report text (paragraph or full document).

**Output:** list of extracted claims, each with a verdict (`VERIFIED` / `REFUTED` / `INSUFFICIENT`), the matched source, and a direct quote.

**Evaluation:** in progress (Phase 3) — accuracy/precision against a 25-claim labeled test set. Numbers land here once the phase ships.

**Demo:** in progress (Phase 4) — link lands here once the UI is deployed.

**Why this stack:** RAG + LLM-as-verifier over structured financial/public data sources is the same core pattern used in production by [Hebbia](https://www.hebbia.com/) (financial due-diligence RAG, 40%+ of large asset managers by AUM), [AuditBoard](https://venturebeat.com/ai/auditboard-upgrades-its-risk-management-platform-with-built-in-llm-descriptions) (LLM-assisted risk/control workflows for internal audit), and Thomson Reuters' Westlaw AI (legal fact-verification — a [Stanford study](https://www.buildmvpfast.com/blog/ai-legal-research-westlaw-lexis-casetext-llms-2026) found it hallucinates 33% of the time, which is exactly the failure mode this project targets).

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
