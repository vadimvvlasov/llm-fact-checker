"""Shared HTTP-JSON transport for ingest/fetch_*.py pipelines."""

import requests


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 15) -> dict:
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
