"""Monitoring dashboard (Phase 4) — 5 charts over logged verification runs.

Mirrors the course's dashboard.py (05-monitoring/code/dashboard.py) role: a
separate page that reads what app.py wrote to Postgres and charts it, instead
of mixing charting into the main verification UI (SRP — app.py stays the
"verify claims" page, this one is the "how is it doing" page). Implemented as
a native Streamlit multipage app (pages/ dir) rather than a second process/
port, so both pages share the same `streamlit run app.py` server and sidebar.
"""

import pandas as pd
import streamlit as st

from src.monitoring import ensure_schema, fetch_feedback, fetch_runs, fetch_verdicts

st.set_page_config(page_title="Fact-Checker — Monitoring", page_icon="📊")
ensure_schema()

st.title("Monitoring dashboard")

runs = pd.DataFrame(fetch_runs())
verdicts = pd.DataFrame(fetch_verdicts())
feedback = pd.DataFrame(fetch_feedback())

if runs.empty:
    st.info("No verification runs logged yet — use the main app to check a report first.")
    st.stop()

st.caption(f"{len(runs)} run(s) · {len(verdicts)} claim(s) checked")

# 1. Verdict distribution
st.subheader("1. Verdict distribution")
st.bar_chart(verdicts["verdict"].value_counts())

# 2. Latency (p95)
st.subheader("2. Latency")
col1, col2 = st.columns(2)
col1.metric("p95 response time", f"{runs['response_time_s'].quantile(0.95):.1f}s")
col2.metric("median response time", f"{runs['response_time_s'].median():.1f}s")
st.line_chart(runs.set_index("created_at")["response_time_s"])

# 3. Feedback ratio
st.subheader("3. Feedback ratio")
if feedback.empty:
    st.caption("No feedback submitted yet.")
else:
    up = int((feedback["score"] > 0).sum())
    down = int((feedback["score"] < 0).sum())
    st.metric("👍 vs 👎", f"{up} / {down}", f"{up / (up + down):.0%} positive" if up + down else None)
    st.bar_chart(pd.Series({"👍 useful": up, "👎 not useful": down}))

# 4. Tokens per query (LLM cost proxy — $0 on the current OpenRouter free tier,
# so token count is the honest cost signal instead of a fake dollar figure)
st.subheader("4. Tokens per query")
col1, col2 = st.columns(2)
col1.metric("avg tokens/run", f"{runs['total_tokens'].mean():.0f}")
col2.metric("avg tokens/claim", f"{(runs['total_tokens'] / runs['num_claims']).mean():.0f}")
st.line_chart(runs.set_index("created_at")["total_tokens"])

# 5. Retrieval hit rate (proxy: share of claims that got a non-INSUFFICIENT
# verdict, i.e. retrieval actually surfaced relevant evidence for the judge)
st.subheader("5. Retrieval hit rate")
hit_rate = (verdicts["verdict"] != "INSUFFICIENT").mean()
st.metric("claims with usable evidence", f"{hit_rate:.0%}")
st.caption(
    "Share of checked claims where retrieval surfaced evidence the judge could act on "
    "(VERIFIED/REFUTED), vs. INSUFFICIENT. Complements the offline hit_rate/MRR numbers "
    "in docs/phase-3-evaluation.md, measured here on live production queries."
)
