"""dlt pipeline: World Bank indicators -> raw staging table (worldbank_raw.worldbank_indicators)."""

import dlt
import requests

from src.config import DATABASE_URL

WB_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "SL.UEM.TOTL.ZS": "Unemployment, total (% of labor force)",
}
WB_COUNTRIES = ["US", "RU", "CN", "DE", "GB", "BR", "IN", "JP"]


@dlt.resource(
    name="worldbank_indicators",
    write_disposition="merge",
    primary_key=["country_code", "indicator_code", "year"],
)
def worldbank_indicators():
    for country in WB_COUNTRIES:
        for code, label in WB_INDICATORS.items():
            url = f"https://api.worldbank.org/v2/country/{country}/indicator/{code}"
            resp = requests.get(url, params={"format": "json", "per_page": 100}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if len(data) < 2 or not data[1]:
                continue
            for row in data[1]:
                if row["value"] is None:
                    continue
                yield {
                    "country": row["country"]["value"],
                    "country_code": country,
                    "indicator_code": code,
                    "indicator_label": label,
                    "year": int(row["date"]),
                    "value": float(row["value"]),
                }


def run():
    pipeline = dlt.pipeline(
        pipeline_name="worldbank_raw",
        destination=dlt.destinations.postgres(credentials=DATABASE_URL),
        dataset_name="worldbank_raw",
    )
    info = pipeline.run(worldbank_indicators())
    print(info)


if __name__ == "__main__":
    run()
