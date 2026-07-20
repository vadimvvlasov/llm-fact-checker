"""Persistence for the Streamlit UI (Phase 4): verification runs + user feedback.

Schema mirrors the LLM Zoomcamp course's monitoring module (05-monitoring/code/db_init.py,
db_save.py, db_feedback.py) — conversations/feedback tables, +1/-1 buttons — adapted to
this project's own connection helper (src/db.py's get_conn, psycopg2) instead of the
course's standalone psycopg3 connection, so there's one place that owns Postgres connections.

`ensure_schema()` uses CREATE TABLE IF NOT EXISTS and is safe to call on every app start,
including against an existing Phase 1-3 database — it does not touch db/init.sql (which
only runs on a fresh container volume and would require dropping already-ingested data).
"""

import psycopg2.extras

from src.db import get_conn
from src.verifier import Verdict


def ensure_schema() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_runs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    report_text TEXT NOT NULL,
                    num_claims INTEGER NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    response_time_s FLOAT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS claim_verdicts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_id UUID REFERENCES verification_runs(id) ON DELETE CASCADE,
                    claim TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    source TEXT,
                    quote TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS run_feedback (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_id UUID REFERENCES verification_runs(id) ON DELETE CASCADE,
                    score INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )


def _sum_usage(usage_records: list[dict]) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for record in usage_records:
        for key in totals:
            totals[key] += (record or {}).get(key, 0) or 0
    return totals


def save_run(
    report_text: str,
    claim_verdicts: list[tuple[str, Verdict]],
    response_time_s: float,
    usage_records: list[dict],
) -> str:
    """claim_verdicts: list of (claim_text, Verdict) pairs, in display order."""
    usage = _sum_usage(usage_records)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO verification_runs
                    (report_text, num_claims, input_tokens, output_tokens, total_tokens, response_time_s)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    report_text,
                    len(claim_verdicts),
                    usage["input_tokens"],
                    usage["output_tokens"],
                    usage["total_tokens"],
                    response_time_s,
                ),
            )
            run_id = cur.fetchone()[0]
            for claim_text, verdict in claim_verdicts:
                cur.execute(
                    """
                    INSERT INTO claim_verdicts (run_id, claim, verdict, source, quote)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, claim_text, verdict.verdict, verdict.source, verdict.quote),
                )
    return run_id


def save_feedback(run_id: str, score: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO run_feedback (run_id, score) VALUES (%s, %s)",
                (run_id, score),
            )


def fetch_runs() -> list[dict]:
    """One row per verification run, for the monitoring dashboard."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, num_claims, input_tokens, output_tokens, total_tokens,
                       response_time_s, created_at
                FROM verification_runs
                ORDER BY created_at
                """
            )
            return [dict(row) for row in cur.fetchall()]


def fetch_verdicts() -> list[dict]:
    """One row per claim verdict, for the verdict-distribution and hit-rate charts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT run_id, claim, verdict, source FROM claim_verdicts")
            return [dict(row) for row in cur.fetchall()]


def fetch_feedback() -> list[dict]:
    """One row per feedback vote, for the feedback-ratio chart."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT run_id, score, created_at FROM run_feedback")
            return [dict(row) for row in cur.fetchall()]
