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
from src.llm import get_usage_log
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

    usage_log = get_usage_log()
    usage_start = len(usage_log)
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
        usage_log[usage_start:],
    )
    total_tokens = sum((usage_log[i] or {}).get("total_tokens", 0) for i in range(usage_start, len(usage_log)))

    # Stashed in session_state (not local vars) so the results survive the rerun
    # triggered by clicking a feedback button below, instead of disappearing.
    st.session_state.run_id = run_id
    st.session_state.feedback_submitted = False
    st.session_state.last_result = {
        "elapsed": elapsed,
        "total_tokens": total_tokens,
        "cards": [
            {"verdict": v.verdict, "claim_text": c.text, "source": v.source, "quote": v.quote}
            for c, v in zip(claims, verdicts)
        ],
    }

if "last_result" in st.session_state:
    result = st.session_state.last_result
    st.caption(f"{len(result['cards'])} claim(s) checked in {result['elapsed']:.1f}s · {result['total_tokens']} tokens")

    for card in result["cards"]:
        icon = VERDICT_ICON[card["verdict"]]
        with st.container(border=True):
            st.markdown(f"**{icon} {card['verdict']}** — {card['claim_text']}")
            if card["source"]:
                st.caption(f"Source: {card['source']}")
            if card["quote"]:
                st.markdown(f"> {card['quote']}")

if "run_id" in st.session_state:
    st.divider()
    if st.session_state.feedback_submitted:
        st.caption("Thanks for the feedback!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍 Useful"):
                save_feedback(st.session_state.run_id, 1)
                st.session_state.feedback_submitted = True
                st.rerun()
        with col2:
            if st.button("👎 Not useful"):
                save_feedback(st.session_state.run_id, -1)
                st.session_state.feedback_submitted = True
                st.rerun()
