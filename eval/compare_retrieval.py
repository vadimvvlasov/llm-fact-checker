"""Compare lexical (minsearch), Postgres full-text, pgvector, hybrid (RRF), and
hybrid+rerank retrieval against data/eval_claims.csv, to see whether a cheap keyword
search is enough or whether vector/hybrid/reranked retrieval earns its extra cost.

Metric per method: hit_rate@k and MRR@k against ground-truth documents derived from each
claim's `source_hint` column. Rows labeled INSUFFICIENT (no matching doc in the KB) are
excluded — there is no correct retrieval target for them.
"""

import csv
import re
from pathlib import Path

from minsearch import Index

from src.db import get_conn, fetch_all_chunks, text_search, vector_search, hybrid_search
from src.embeddings import embed_texts
from src.rerank import rerank

EVAL_CSV = Path(__file__).resolve().parent.parent / "data" / "eval_claims.csv"
TOP_K = 5
RERANK_K = 3  # matches verify_claim's real top-5 -> top-3 rerank width

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


def score(name: str, claims: list[dict], retrieve_fn, k: int = TOP_K) -> None:
    hits, rr_sum = 0, 0.0
    for claim in claims:
        results = retrieve_fn(claim["claim"])
        rank = hit_rank(results, claim["source_hint"])
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(claims)
    print(f"{name:>13}: hit_rate@{k}={hits}/{n} ({hits / n:.0%})   MRR@{k}={rr_sum / n:.3f}")


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

    def pg_hybrid_rerank_retrieve(query: str) -> list[dict]:
        return rerank(query, pg_hybrid_retrieve(query), top_k=RERANK_K)

    score("minsearch", claims, minsearch_retrieve)
    score("pg_text", claims, pg_text_retrieve)
    score("pg_vector", claims, pg_vector_retrieve)
    score("hybrid_rrf", claims, pg_hybrid_retrieve)
    score("hybrid_rerank", claims, pg_hybrid_rerank_retrieve, k=RERANK_K)


if __name__ == "__main__":
    main()
