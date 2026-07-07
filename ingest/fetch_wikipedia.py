"""dlt pipeline: financial/economic Wikipedia articles -> raw staging table (wikipedia_raw.wikipedia_articles).

Uses the MediaWiki API directly (the `wikipedia` PyPI package is unmaintained and breaks
against Wikipedia's current API, which now requires a User-Agent — see
https://phabricator.wikimedia.org/T400119).
"""

import dlt

from ingest.http import get_json
from src.config import DATABASE_URL

USER_AGENT = "llm-fact-checker/0.1 (LLM Zoomcamp capstone; https://github.com/vadimvvlasov)"

WIKI_TOPICS = [
    "Gross domestic product",
    "Inflation",
    "Unemployment",
    "Federal Reserve",
    "Stock market",
    "Corporate bond",
    "Balance sheet",
    "Income statement",
    "Cash flow statement",
    "Earnings per share",
    "Price–earnings ratio",
    "Return on equity",
    "Debt-to-equity ratio",
    "Market capitalization",
    "Initial public offering",
    "Mergers and acquisitions",
    "Dividend",
    "Bear market",
    "Bull market",
    "Recession",
    "Economic indicator",
    "Consumer price index",
    "Interest rate",
    "Monetary policy",
    "Fiscal policy",
    "Sovereign wealth fund",
    "Credit rating agency",
    "Hedge fund",
    "Private equity",
    "Venture capital",
]


def fetch_wikipedia_article(title: str) -> dict | None:
    """Fetch a single article's plaintext extract via the MediaWiki API."""
    data = get_json(
        "https://en.wikipedia.org/w/api.php",
        headers={"User-Agent": USER_AGENT},
        params={
            "action": "query",
            "prop": "extracts|info",
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
            "titles": title,
            "format": "json",
        },
    )
    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1" or "extract" not in page:
            return None
        return {
            "title": page["title"],
            "url": page.get("fullurl", f"https://en.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"),
            "content": page["extract"],
        }
    return None


@dlt.resource(name="wikipedia_articles", write_disposition="merge", primary_key="title")
def wikipedia_articles():
    for topic in WIKI_TOPICS:
        try:
            article = fetch_wikipedia_article(topic)
        except Exception as e:
            print(f"skip '{topic}': {e}")
            continue
        if article is None:
            print(f"skip '{topic}': no extract returned")
            continue
        yield article


def run():
    pipeline = dlt.pipeline(
        pipeline_name="wikipedia_raw",
        destination=dlt.destinations.postgres(credentials=DATABASE_URL),
        dataset_name="wikipedia_raw",
    )
    info = pipeline.run(wikipedia_articles())
    print(info)


if __name__ == "__main__":
    run()
