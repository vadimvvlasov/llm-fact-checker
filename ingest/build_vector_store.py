"""Reads raw staging tables (loaded by dlt) -> chunks + embeds -> documents/document_chunks."""

import psycopg2
import psycopg2.extras

from src.chunking import chunk_text
from src.config import DATABASE_URL
from src.db import get_conn, insert_chunks, insert_document, count_chunks
from src.embeddings import embed_texts


def _raw_conn():
    return psycopg2.connect(DATABASE_URL)


def load_wikipedia():
    with _raw_conn() as raw, raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT title, url, content FROM wikipedia_raw.wikipedia_articles')
        rows = cur.fetchall()

    total_chunks = 0
    with get_conn() as conn:
        for row in rows:
            chunks = chunk_text(row["content"], sentences_per_chunk=4, overlap=1)
            if not chunks:
                continue
            embeddings = embed_texts(chunks)
            doc_id = insert_document(conn, title=row["title"], source="wikipedia", doc_type="article", url=row["url"])
            insert_chunks(conn, doc_id, chunks, embeddings, metadata={"source": "wikipedia", "title": row["title"]})
            total_chunks += len(chunks)
    print(f"wikipedia: {len(rows)} articles -> {total_chunks} chunks")


def load_worldbank():
    with _raw_conn() as raw, raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT country, country_code, indicator_code, indicator_label, year, value "
            "FROM worldbank_raw.worldbank_indicators ORDER BY country_code, indicator_code, year"
        )
        rows = cur.fetchall()

    groups: dict[tuple, list] = {}
    for row in rows:
        key = (row["country_code"], row["indicator_code"])
        groups.setdefault(key, []).append(row)

    total_chunks = 0
    with get_conn() as conn:
        for (country_code, indicator_code), group_rows in groups.items():
            label = group_rows[0]["indicator_label"]
            country = group_rows[0]["country"]
            facts = [
                f"{label} for {country} in {r['year']} was {r['value']:.2f}."
                for r in group_rows
            ]
            embeddings = embed_texts(facts)
            doc_id = insert_document(
                conn,
                title=f"{label} — {country}",
                source="worldbank",
                doc_type="indicator_series",
                url=f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}",
            )
            metadata = {"source": "worldbank", "country": country, "indicator_code": indicator_code}
            insert_chunks(conn, doc_id, facts, embeddings, metadata=metadata)
            total_chunks += len(facts)
    print(f"worldbank: {len(groups)} series -> {total_chunks} chunks")


def load_fred():
    try:
        with _raw_conn() as raw, raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT series_id, series_label, date, value FROM fred_raw.fred_series ORDER BY series_id, date"
            )
            rows = cur.fetchall()
    except psycopg2.errors.UndefinedTable:
        print("fred: no data yet (run ingest/fetch_fred.py with FRED_API_KEY first) — skipping")
        return

    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row["series_id"], []).append(row)

    total_chunks = 0
    with get_conn() as conn:
        for series_id, group_rows in groups.items():
            label = group_rows[0]["series_label"]
            facts = [f"{label} ({series_id}) on {r['date']} was {r['value']}." for r in group_rows]
            embeddings = embed_texts(facts)
            doc_id = insert_document(
                conn,
                title=f"{label} ({series_id})",
                source="fred",
                doc_type="indicator_series",
                url=f"https://fred.stlouisfed.org/series/{series_id}",
            )
            metadata = {"source": "fred", "series_id": series_id}
            insert_chunks(conn, doc_id, facts, embeddings, metadata=metadata)
            total_chunks += len(facts)
    print(f"fred: {len(groups)} series -> {total_chunks} chunks")


def load_secedgar():
    try:
        with _raw_conn() as raw, raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT ticker, company_name, tag, fiscal_year_end, value_usd, form, filed "
                "FROM secedgar_raw.sec_facts ORDER BY ticker, tag, fiscal_year_end"
            )
            rows = cur.fetchall()
    except psycopg2.errors.UndefinedTable:
        print("secedgar: no data yet (run ingest/fetch_secedgar.py first) — skipping")
        return

    groups: dict[tuple, list] = {}
    for row in rows:
        groups.setdefault((row["ticker"], row["tag"]), []).append(row)

    total_chunks = 0
    with get_conn() as conn:
        for (ticker, tag), group_rows in groups.items():
            company_name = group_rows[0]["company_name"]
            facts = [
                f"{company_name} ({ticker}) reported {tag} of ${r['value_usd']:,.0f} "
                f"for fiscal year ending {r['fiscal_year_end']} ({r['form']} filed {r['filed']})."
                for r in group_rows
            ]
            embeddings = embed_texts(facts)
            doc_id = insert_document(
                conn,
                title=f"{company_name} ({ticker}) — {tag}",
                source="secedgar",
                doc_type="10-K financial facts",
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}",
            )
            metadata = {"source": "secedgar", "ticker": ticker, "tag": tag}
            insert_chunks(conn, doc_id, facts, embeddings, metadata=metadata)
            total_chunks += len(facts)
    print(f"secedgar: {len(groups)} series -> {total_chunks} chunks")


def run():
    load_wikipedia()
    load_worldbank()
    load_fred()
    load_secedgar()
    with get_conn() as conn:
        print(f"TOTAL chunks in vector store: {count_chunks(conn)}")


if __name__ == "__main__":
    run()
