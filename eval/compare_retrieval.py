"""Compare lexical (minsearch), Postgres full-text, pgvector, and hybrid (RRF) retrieval
against data/eval_claims.csv, to see whether a cheap keyword search is enough or whether
vector/hybrid retrieval earns its extra infra cost.

Metric per method: hit_rate@5 and MRR@5 against ground-truth documents derived from each
claim's `source_hint` column. Rows labeled INSUFFICIENT (no matching doc in the KB) are
excluded — there is no correct retrieval target for them.
"""

import csv
import re
from pathlib import Path

from minsearch import Index

from src.db import get_conn, fetch_all_chunks, text_search, vector_search, hybrid_search
from src.embeddings import embed_texts

EVAL_CSV = Path(__file__).resolve().parent.parent / "data" / "eval_claims.csv"
TOP_K = 5

WB_CODE_TO_NAME = {
    "US": "United States", "RU": "Russian Federation", "CN": "China", "DE": "Germany",
    "GB": "United Kingdom", "BR": "Brazil", "IN": "India", "JP": "Japan",
}
WB_LABEL_TO_CODE = {
    "GDP": "NY.GDP.MKTP.CD",
    "Inflation": "FP.CPI.TOTL.ZG",
    "Unemployment": "SL.UEM.TOTL.ZS",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def load_claims() -> list[dict]:
    with open(EVAL_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["expected_verdict"] != "INSUFFICIENT"]


def is_relevant(row: dict, source_hint: str) -> bool:
    """row: a retrieved chunk dict with 'source', 'metadata', 'title'. source_hint: golden-set hint."""
    source = source_hint.split(":", 1)[0]
    if row["source"] != source:
        return False
    meta = row["metadata"] or {}

    if source == "secedgar":
        _, ticker, tag = source_hint.split(":", 2)
        tag = tag.split(" (")[0].strip()
        return meta.get("ticker") == ticker and meta.get("tag") == tag

    if source == "worldbank":
        _, code, indicator = source_hint.split(":", 2)
        indicator = indicator.split(" (")[0].strip()
        return (
            meta.get("country") == WB_CODE_TO_NAME.get(code)
            and meta.get("indicator_code") == WB_LABEL_TO_CODE.get(indicator)
        )

    if source == "wikipedia":
        topic = source_hint.split(":", 1)[1].split(" (")[0].strip()
        return _normalize(topic) in _normalize(row["title"])

    return False


def hit_rank(results: list[dict], source_hint: str) -> int | None:
    """1-based rank of the first relevant result, or None if no hit in top-k."""
    for i, row in enumerate(results):
        if is_relevant(row, source_hint):
            return i + 1
    return None


def score(name: str, claims: list[dict], retrieve_fn) -> None:
    hits, rr_sum = 0, 0.0
    for claim in claims:
        results = retrieve_fn(claim["claim"])
        rank = hit_rank(results, claim["source_hint"])
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(claims)
    print(f"{name:>12}: hit_rate@{TOP_K}={hits}/{n} ({hits / n:.0%})   MRR@{TOP_K}={rr_sum / n:.3f}")


def main():
    claims = load_claims()
    print(f"evaluating on {len(claims)} claims (INSUFFICIENT rows excluded)\n")

    with get_conn() as conn:
        chunks = fetch_all_chunks(conn)

    minsearch_index = Index(text_fields=["content", "title"], keyword_fields=["source"])
    minsearch_index.fit(chunks)

    def minsearch_retrieve(query: str) -> list[dict]:
        return minsearch_index.search(query, num_results=TOP_K, boost_dict={"title": 2.0})

    def pg_text_retrieve(query: str) -> list[dict]:
        with get_conn() as conn:
            return text_search(conn, query, top_k=TOP_K)

    def pg_vector_retrieve(query: str) -> list[dict]:
        embedding = embed_texts([query])[0]
        with get_conn() as conn:
            return vector_search(conn, embedding, top_k=TOP_K)

    def pg_hybrid_retrieve(query: str) -> list[dict]:
        embedding = embed_texts([query])[0]
        with get_conn() as conn:
            return hybrid_search(conn, query, embedding, top_k=TOP_K)

    score("minsearch", claims, minsearch_retrieve)
    score("pg_text", claims, pg_text_retrieve)
    score("pg_vector", claims, pg_vector_retrieve)
    score("hybrid_rrf", claims, pg_hybrid_retrieve)


if __name__ == "__main__":
    main()
