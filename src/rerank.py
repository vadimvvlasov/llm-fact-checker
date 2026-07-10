from functools import lru_cache

from sentence_transformers import CrossEncoder

from src.config import RERANK_MODEL


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    return CrossEncoder(RERANK_MODEL)


def rerank(query: str, chunks: list[dict], top_k: int = 3) -> list[dict]:
    """Re-score retrieved chunks against the query with a cross-encoder, keep the top_k."""
    if not chunks:
        return []
    pairs = [(query, c["content"]) for c in chunks]
    scores = get_reranker().predict(pairs)
    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    return [{**c, "rerank_score": float(s)} for c, s in ranked[:top_k]]
