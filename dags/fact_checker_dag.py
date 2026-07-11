"""Airflow DAG: daily refresh of the fact-checker knowledge base.

Input:  nothing but the schedule trigger + secrets from .env (FRED_API_KEY,
        etc., injected via docker-compose env_file). Each ingest module's
        dlt resource is `write_disposition="merge"` on its own primary key,
        so re-running a fetch is idempotent — no duplicate rows.
Output: refreshed `*_raw` schemas (wikipedia_raw, worldbank_raw, fred_raw,
        secedgar_raw) in Postgres, followed by a full truncate-and-rebuild
        of the derived vector store (`documents` / `document_chunks`) that
        `src/db.py`'s hybrid search reads from.

Design: this file is pure orchestration. It imports each ingest module's
existing `run()` entrypoint and does not reimplement fetch/chunk/embed
logic — that already lives in ingest/fetch_*.py and
ingest/build_vector_store.py (single responsibility per module). Adding a
new source later means one new ingest/fetch_*.py + one new task below;
no existing task changes (open/closed). The four fetch tasks don't depend
on each other (independent sources); `rebuild_vector_store` depends on all
four because it re-reads every *_raw table from scratch on each run.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from ingest import build_vector_store, fetch_fred, fetch_secedgar, fetch_wikipedia, fetch_worldbank

FETCH_MODULES = {
    "wikipedia": fetch_wikipedia,
    "worldbank": fetch_worldbank,
    "fred": fetch_fred,
    "secedgar": fetch_secedgar,
}

with DAG(
    dag_id="fact_checker_daily_ingestion",
    description="Refresh the 4 source tables, then rebuild the vector store",
    schedule="@daily",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    default_args={"retries": 1},
    tags=["fact-checker", "ingestion"],
) as dag:
    fetch_tasks = [
        PythonOperator(task_id=f"fetch_{name}", python_callable=module.run)
        for name, module in FETCH_MODULES.items()
    ]

    rebuild_vector_store = PythonOperator(
        task_id="rebuild_vector_store",
        python_callable=build_vector_store.run,
    )

    fetch_tasks >> rebuild_vector_store
