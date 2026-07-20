"""Streamlit UI (Phase 4) — claim input -> verdict cards with sources.

Structure follows the LLM Zoomcamp course's monitoring module
(05-monitoring/code/app.py): text input -> spinner -> answer -> response
time/tokens -> save to DB -> +1/-1 feedback buttons. Adapted here for
multi-claim output (one card per claim) instead of a single chat answer.

UI stays presentation-only (SRP): claim extraction and verification logic
live in src/claim_extractor.py and src/verifier.py, persistence lives in
src/monitoring.py — this file just wires them together for display.

See pages/1_Monitoring.py for the metrics dashboard (verdict distribution,
latency, feedback ratio, tokens/query, retrieval hit rate) — a second
Streamlit page in the same app, reachable from the sidebar.
"""

import time

import streamlit as st

from src.claim_extractor import extract_claims
from src.llm import USAGE_LOG
from src.monitoring import ensure_schema, save_feedback, save_run
from src.verifier import verify_claim

VERDICT_ICON = {"VERIFIED": "✅", "REFUTED": "❌", "INSUFFICIENT": "❓"}

st.set_page_config(page_title="Fact-Checker RAG", page_icon="✅")
ensure_schema()

st.title("Business Report Fact-Checker")
st.caption(
    "Paste report text with factual claims (a number tied to an entity, e.g. revenue, "
    "GDP, inflation). Each claim is checked against the knowledge base."
)

report_text = st.text_area(
    "Report text",
    height=200,
    placeholder="Apple's revenue was $391 billion in fiscal year 2024. US GDP grew 2.8% in 2024.",
)

if st.button("Verify claims", type="primary"):
    if not report_text.strip():
        st.warning("Paste some report text first.")
        st.stop()

    usage_start = len(USAGE_LOG)
    start = time.time()
    with st.spinner("Extracting claims and checking evidence..."):
        claims = extract_claims(report_text)
        verdicts = [verify_claim(claim) for claim in claims]
    elapsed = time.time() - start

    if not claims:
        st.info("No checkable claims found in this text.")
        st.stop()

    run_id = save_run(
        report_text,
        list(zip((c.text for c in claims), verdicts)),
        elapsed,
        USAGE_LOG[usage_start:],
    )
    st.session_state.run_id = run_id

    total_tokens = sum((USAGE_LOG[i] or {}).get("total_tokens", 0) for i in range(usage_start, len(USAGE_LOG)))
    st.caption(f"{len(claims)} claim(s) checked in {elapsed:.1f}s · {total_tokens} tokens")

    for claim, verdict in zip(claims, verdicts):
        icon = VERDICT_ICON[verdict.verdict]
        with st.container(border=True):
            st.markdown(f"**{icon} {verdict.verdict}** — {claim.text}")
            if verdict.source:
                st.caption(f"Source: {verdict.source}")
            if verdict.quote:
                st.markdown(f"> {verdict.quote}")

if "run_id" in st.session_state:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 Useful"):
            save_feedback(st.session_state.run_id, 1)
            st.success("Thanks!")
    with col2:
        if st.button("👎 Not useful"):
            save_feedback(st.session_state.run_id, -1)
            st.success("Thanks for the feedback!")
