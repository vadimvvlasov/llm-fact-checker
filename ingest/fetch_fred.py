"""dlt pipeline: FRED macro series -> raw staging table (fred_raw.fred_series). Needs FRED_API_KEY."""

import dlt

from ingest.http import get_json
from src.config import DATABASE_URL, FRED_API_KEY

FRED_SERIES = {
    "GDP": "Gross Domestic Product",
    "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Federal Funds Effective Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
}


def fetch_fred_series(series_id: str, label: str) -> list[dict]:
    """Fetch one FRED series and shape it into staging rows."""
    data = get_json(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": "2015-01-01",
        },
    )
    return [
        {
            "series_id": series_id,
            "series_label": label,
            "date": obs["date"],
            "value": float(obs["value"]),
        }
        for obs in data.get("observations", [])
        if obs["value"] != "."
    ]


@dlt.resource(name="fred_series", write_disposition="merge", primary_key=["series_id", "date"])
def fred_series():
    if not FRED_API_KEY:
        raise RuntimeError(
            "FRED_API_KEY not set. Get a free key: https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    for series_id, label in FRED_SERIES.items():
        yield from fetch_fred_series(series_id, label)


def run():
    pipeline = dlt.pipeline(
        pipeline_name="fred_raw",
        destination=dlt.destinations.postgres(credentials=DATABASE_URL),
        dataset_name="fred_raw",
    )
    info = pipeline.run(fred_series())
    print(info)


if __name__ == "__main__":
    run()
