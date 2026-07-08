from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from src.config import DATABASE_URL


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_document(conn, title: str, source: str, doc_type: str, url: str | None) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (title, source, doc_type, url)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (title, source, doc_type, url),
        )
        return cur.fetchone()[0]


def insert_chunks(conn, document_id: str, chunks: list[str], embeddings: list[list[float]], metadata: dict):
    with conn.cursor() as cur:
        for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, content, embedding, metadata, chunk_index)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (document_id, content, embedding, psycopg2.extras.Json(metadata), idx),
            )


def count_chunks(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks")
        return cur.fetchone()[0]


def fetch_all_chunks(conn) -> list[dict]:
    """All chunks joined with their document, for building an in-memory index (e.g. minsearch)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT c.id, c.content, c.metadata, d.title, d.source, d.doc_type
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def text_search(conn, query: str, top_k: int = 5) -> list[dict]:
    """Lexical retrieval via Postgres full-text search (ts_rank on content_tsv)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT c.id, c.content, c.metadata, d.title, d.source,
                   ts_rank(c.content_tsv, query) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id,
                 to_tsquery('english', %s) query
            WHERE c.content_tsv @@ query
            ORDER BY score DESC
            LIMIT %s
            """,
            (_to_tsquery_input(query), top_k),
        )
        return [dict(row) for row in cur.fetchall()]


def vector_search(conn, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Semantic retrieval via pgvector cosine distance."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT c.id, c.content, c.metadata, d.title, d.source,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, top_k),
        )
        return [dict(row) for row in cur.fetchall()]


def hybrid_search(conn, query: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Combine text + vector rankings via Reciprocal Rank Fusion (RRF, k=60)."""
    text_results = text_search(conn, query, top_k=top_k * 3)
    vector_results = vector_search(conn, query_embedding, top_k=top_k * 3)

    rrf_scores: dict[str, float] = {}
    rows_by_id: dict[str, dict] = {}
    for results in (text_results, vector_results):
        for rank, row in enumerate(results):
            rrf_scores[row["id"]] = rrf_scores.get(row["id"], 0.0) + 1.0 / (60 + rank + 1)
            rows_by_id[row["id"]] = row

    ranked_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    return [{**rows_by_id[rid], "score": rrf_scores[rid]} for rid in ranked_ids]


def _to_tsquery_input(query: str) -> str:
    """Turn a free-text query into an OR-tsquery so partial keyword overlap still matches."""
    words = [w for w in query.replace("'", " ").split() if w]
    return " | ".join(words) if words else query
