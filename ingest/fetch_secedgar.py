"""dlt pipeline: SEC EDGAR company facts (10-K annual figures) -> raw staging table (secedgar_raw.sec_facts).

Uses the free XBRL Company Facts API. SEC requires a descriptive User-Agent with contact info.
Docs: https://www.sec.gov/os/webmaster-faq#developers
"""

from datetime import date

import dlt
import requests

from src.config import DATABASE_URL

USER_AGENT = "llm-fact-checker vadim.v.vlasov@gmail.com"

TICKERS = ["AAPL", "MSFT", "AMZN", "TSLA", "GOOGL", "META", "JPM", "WMT"]

# tag -> human label. Revenue has two possible XBRL tags depending on filer; try both.
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]
OTHER_TAGS = {
    "NetIncomeLoss": "Net income",
    "Assets": "Total assets",
}


def _get(url: str) -> dict:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def resolve_cik(ticker: str, ticker_map: dict) -> tuple[str, str] | None:
    for row in ticker_map.values():
        if row["ticker"] == ticker:
            return f"{row['cik_str']:010d}", row["title"]
    return None


def annual_values(units: list[dict]) -> list[dict]:
    """Keep one value per full fiscal year, from 10-K filings, deduped by period end (latest filed wins)."""
    candidates: dict[str, dict] = {}
    for u in units:
        if u.get("form") != "10-K":
            continue
        end = u.get("end")
        start = u.get("start")
        if not end:
            continue
        if start:
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if not (350 <= days <= 380):
                continue  # skip quarterly/partial-year comparatives
        if end not in candidates or u["filed"] > candidates[end]["filed"]:
            candidates[end] = u
    return sorted(candidates.values(), key=lambda u: u["end"])


@dlt.resource(name="sec_facts", write_disposition="merge", primary_key=["ticker", "tag", "fiscal_year_end"])
def sec_facts():
    ticker_map = _get("https://www.sec.gov/files/company_tickers.json")

    for ticker in TICKERS:
        resolved = resolve_cik(ticker, ticker_map)
        if resolved is None:
            print(f"skip {ticker}: not found in company_tickers.json")
            continue
        cik, company_name = resolved

        try:
            facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        except Exception as e:
            print(f"skip {ticker}: {e}")
            continue

        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        # revenue: companies switch XBRL tags over time (ASC 606 transition) — merge both,
        # dedupe by period end (latest filed wins) so we get full history, not just one tag's years.
        revenue_by_end: dict[str, dict] = {}
        for tag in REVENUE_TAGS:
            if tag not in us_gaap or "USD" not in us_gaap[tag]["units"]:
                continue
            for row in annual_values(us_gaap[tag]["units"]["USD"]):
                end = row["end"]
                if end not in revenue_by_end or row["filed"] > revenue_by_end[end]["filed"]:
                    revenue_by_end[end] = row
        for row in sorted(revenue_by_end.values(), key=lambda r: r["end"]):
            yield {
                "ticker": ticker,
                "company_name": company_name,
                "cik": cik,
                "tag": "Revenue",
                "fiscal_year_end": row["end"],
                "value_usd": row["val"],
                "form": row["form"],
                "filed": row["filed"],
            }

        for tag, label in OTHER_TAGS.items():
            if tag not in us_gaap or "USD" not in us_gaap[tag]["units"]:
                continue
            for row in annual_values(us_gaap[tag]["units"]["USD"]):
                yield {
                    "ticker": ticker,
                    "company_name": company_name,
                    "cik": cik,
                    "tag": label,
                    "fiscal_year_end": row["end"],
                    "value_usd": row["val"],
                    "form": row["form"],
                    "filed": row["filed"],
                }


def run():
    pipeline = dlt.pipeline(
        pipeline_name="secedgar_raw",
        destination=dlt.destinations.postgres(credentials=DATABASE_URL),
        dataset_name="secedgar_raw",
    )
    info = pipeline.run(sec_facts())
    print(info)


if __name__ == "__main__":
    run()
