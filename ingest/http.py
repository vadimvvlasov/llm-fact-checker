"""Shared HTTP-JSON transport for ingest/fetch_*.py pipelines."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sources like World Bank get hit with 24 sequential requests per run
# (fetch_worldbank: 8 countries x 3 indicators) — one transient timeout used
# to fail the whole task and force a full dlt re-extraction. Retry+backoff
# here covers all 4 fetch_*.py callers from one place.
_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])),
)


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 30) -> dict:
    resp = _session.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
