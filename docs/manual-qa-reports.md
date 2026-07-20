# Manual QA — sample report texts for the Streamlit UI

27 paste-in blocks for manually smoke-testing `app.py` (`uv run streamlit run app.py`
→ paste one block into "Report text" → "Verify claims"). Each block is built from
claims already validated in `data/eval_claims.csv` (Phase 3 eval set), so the
expected verdict and expected retrieval hit/miss are known ahead of time —
this isn't guessing, it's re-using ground truth from the labeled eval set.

**Expected aggregate retrieval hit rate: 54/60 claims = 90%** (a "hit" = the
dashboard's definition: any VERIFIED or REFUTED verdict, i.e. retrieval
surfaced usable evidence; only INSUFFICIENT counts as a miss). 6 claims across
blocks 11, 17, 22, 27 are intentionally INSUFFICIENT — keep them in to also
exercise that code path, not just the happy path.

Each block lists the source `eval_claims.csv` row IDs in a comment after it —
that's for you to check the app's verdict against, not part of the pasted text.

## SEC EDGAR — company financials

**1.** Apple's revenue for fiscal year ending 2025-09-27 was $416,161,000,000. Apple's net income for fiscal year ending 2025-09-27 was $112,010,000,000.
<!-- ids 1,2 — VERIFIED, VERIFIED -->

**2.** Microsoft's total assets for fiscal year ending 2025-06-30 were $619,003,000,000. Apple's total assets for fiscal year ending 2022-09-24 were $352,755,000,000.
<!-- ids 3,26 — VERIFIED, VERIFIED -->

**3.** Amazon's revenue for fiscal year ending 2025-12-31 was $716,924,000,000. Amazon's total assets for fiscal year ending 2025-12-31 were $200,000,000,000.
<!-- ids 4,14 — VERIFIED, REFUTED (real total assets 818.042B) -->

**4.** JPMorgan Chase's total assets for fiscal year ending 2025-12-31 were $4,424,900,000,000. JPMorgan Chase's net income for fiscal year ending 2022-12-31 was $37,676,000,000.
<!-- ids 5,29 — VERIFIED, VERIFIED -->

**5.** Tesla's net income for fiscal year ending 2025-12-31 was $3,794,000,000. Tesla's revenue for fiscal year ending 2025-12-31 was $200,000,000,000.
<!-- ids 6,16 — VERIFIED, REFUTED (real revenue 94.827B) -->

**6.** Walmart's revenue for fiscal year ending 2026-01-31 was $713,163,000,000. Walmart's net income for fiscal year ending 2026-01-31 was $80,000,000,000.
<!-- ids 7,17 — VERIFIED, REFUTED (real net income 21.893B) -->

**7.** Meta's net income for fiscal year ending 2025-12-31 was $60,458,000,000. Meta's total assets for fiscal year ending 2021-12-31 were $165,987,000,000.
<!-- ids 8,30 — VERIFIED, VERIFIED -->

**8.** Alphabet's revenue for fiscal year ending 2022-12-31 was $282,836,000,000. Alphabet's revenue for fiscal year ending 2022-12-31 was $600,000,000,000.
<!-- ids 28,37 — VERIFIED, REFUTED (contradicting figure for the same period, on purpose) -->

**9.** Microsoft's revenue for fiscal year ending 2021-06-30 was $168,088,000,000. Microsoft's revenue for fiscal year ending 2021-06-30 was $300,000,000,000.
<!-- ids 31,40 — VERIFIED, REFUTED -->

**10.** Amazon's net income for fiscal year ending 2021-12-31 was $33,364,000,000. Amazon's net income for fiscal year ending 2021-12-31 was $80,000,000,000.
<!-- ids 27,36 — VERIFIED, REFUTED -->

**11.** Amazon reported a net loss of approximately $2.72 billion for fiscal year ending 2022-12-31. Netflix's revenue for fiscal year 2025 was $39 billion.
<!-- ids 34,22 — VERIFIED (negative-value edge case), INSUFFICIENT (Netflix not in TICKERS) -->

## World Bank — macro indicators

**12.** US GDP in 2025 was approximately $30.77 trillion. US GDP in 2025 was approximately $10 trillion.
<!-- ids 9,18 — VERIFIED, REFUTED -->

**13.** Germany's unemployment rate in 2025 was 4.0%. Brazil's unemployment rate in 2025 was 20.0%.
<!-- ids 10,48 — VERIFIED, REFUTED (real 6.0%) -->

**14.** Japan's inflation rate in 2025 was 3.0%. Germany's inflation rate in 2025 was 12.0%.
<!-- ids 11,19 — VERIFIED, REFUTED (real 2.0%) -->

**15.** Brazil's unemployment rate in 2025 was 6.0%. China's inflation rate in 2025 was 0.0%.
<!-- ids 43,44 — VERIFIED, VERIFIED -->

**16.** The United Kingdom's GDP in 2025 was approximately $4.0 trillion. India's unemployment rate in 2025 was 4.0%. Russia's inflation rate in 2025 was 9.0%.
<!-- ids 45,46,47 — VERIFIED, VERIFIED, VERIFIED -->

**17.** Russia's GDP in 2025 was approximately $500 billion. South Korea's GDP in 2025 was approximately $1.8 trillion.
<!-- ids 50,51 — REFUTED (real ~2.56T), INSUFFICIENT (South Korea not in WB_COUNTRIES) -->

## FRED — US macro time series

**18.** US GDP in the third quarter of 2019 was about $21.7 trillion. US GDP in the third quarter of 2022 was about $15 trillion.
<!-- ids 53,54 — VERIFIED, REFUTED (real ~$26.3T) -->

**19.** The US unemployment rate was 7.8% in September 2020, reflecting pandemic-era job losses. The US unemployment rate was around 8% in October 2018.
<!-- ids 55,56 — VERIFIED, REFUTED (real 3.8%) -->

**20.** The Federal Reserve's effective funds rate was about 5.08% in June 2023. The Fed funds rate was already above 4% by January 2022.
<!-- ids 57,58 — VERIFIED, REFUTED (real 0.08%) -->

**21.** The 10-year US Treasury yield reached roughly 4.86% in late October 2023. The 10-year Treasury yield was near 3% in late April 2020.
<!-- ids 59,60 — VERIFIED, REFUTED (real 0.6%) -->

**22.** The US Consumer Price Index stood at about 309.7 in January 2024. US CPI had already climbed past 280 by April 2016. The Bank of Japan's policy interest rate was -0.1% throughout 2023.
<!-- ids 61,62,63 — VERIFIED, REFUTED (real 238.992), INSUFFICIENT (no BOJ series ingested) -->

## Wikipedia — financial concepts/definitions

**23.** A balance sheet reports a company's assets, liabilities, and owner's equity at a single point in time. A cash flow statement shows how a company's cash position changes due to operating, investing, and financing activities.
<!-- ids 65,66 — VERIFIED, VERIFIED -->

**24.** The debt-to-equity ratio is found by dividing a company's total assets by its shareholders' equity. A dividend is a portion of a corporation's profit distributed to its shareholders. Earnings per share is calculated by dividing a company's total revenue by its number of outstanding shares.
<!-- ids 67,68,69 — REFUTED (actual: debt/equity, not assets/equity), VERIFIED, REFUTED (actual: net earnings, not revenue) -->

**25.** An income statement reports a company's revenues and expenses over a specific period of time. Market capitalization is calculated by multiplying a company's annual revenue by its profit margin. Return on equity measures profitability by dividing net income by average shareholders' equity.
<!-- ids 70,71,72 — VERIFIED, REFUTED (actual: share price × shares outstanding), VERIFIED -->

**26.** Monetary policy refers to actions a central bank takes to influence financial conditions in pursuit of goals like stable prices and high employment. According to the IMF, a recession is officially defined as two consecutive quarters of GDP decline. An interest rate expresses the cost of borrowing as a proportion of the amount lent, usually on an annualized basis.
<!-- ids 73,74,75 — VERIFIED, REFUTED (IMF has no official definition), VERIFIED -->

## Known-miss block — exercises the INSUFFICIENT path on purpose

**27.** A leveraged buyout uses a target company's own assets as collateral to finance its acquisition. Apple's revenue for fiscal year 2010 was $65 billion. NVIDIA's net income for fiscal year 2025 was $30 billion.
<!-- ids 76,24,25 — all INSUFFICIENT (not indexed / not in TICKERS / dedup drops old filings) -->
