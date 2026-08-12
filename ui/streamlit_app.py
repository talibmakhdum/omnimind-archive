"""OmniMind Archive Streamlit UI."""

from __future__ import annotations

import os
import time

import requests
import streamlit as st

API = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="OmniMind Archive", layout="wide")

if "search_id" not in st.session_state:
    st.session_state.search_id = None
if "ingest_id" not in st.session_state:
    st.session_state.ingest_id = None

st.title("OmniMind Archive")
st.markdown("Privacy-first semantic search for your chat exports. Local-only by default.")

with st.sidebar:
    st.header("Upload export")
    uploaded_file = st.file_uploader(
        "ChatGPT export (.json)",
        type=["json"],
        help="Settings → Data controls → Export",
    )
    source_platform = st.selectbox("Source platform", ["chatgpt", "gemini", "deepseek", "arena"])
    st.markdown("### Consent")
    tos_checked = st.checkbox(
        "I have read the platform Terms of Service (https://openai.com/terms/)",
        value=False,
    )
    consent_checked = st.checkbox(
        "I consent to process and store this data locally on this device only",
        value=False,
    )
    if uploaded_file and tos_checked and consent_checked:
        if st.button("Start ingestion"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/json")}
            data = {
                "source_platform": source_platform,
                "tos_url": "https://openai.com/terms/",
                "tos_version": "2024-01-15",
                "consent_given": "true",
            }
            try:
                response = requests.post(f"{API}/ingest", files=files, data=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                st.session_state.ingest_id = result["ingest_id"]
                st.success(f"Queued: {result['ingest_id']}")
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

    if st.session_state.ingest_id:
        st.markdown("### Ingest status")
        try:
            status_resp = requests.get(
                f"{API}/ingest/{st.session_state.ingest_id}/status", timeout=10
            )
            status_data = status_resp.json()
            progress = status_data.get("progress_pct") or 0
            st.progress(min(progress / 100, 1.0))
            st.markdown(f"**Status:** {status_data.get('status')}")
            if status_data.get("status") == "completed":
                st.success("Ingest complete")
            if status_data.get("error"):
                st.error(status_data["error"])
        except Exception as exc:
            st.warning(f"Could not fetch status: {exc}")

st.header("Search & RAG")
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    query = st.text_input("Search your archive", placeholder="machine learning basics")
with col2:
    top_k = st.number_input("Top K", value=10, min_value=1, max_value=50)
with col3:
    redact = st.selectbox("Redact", ["min", "none", "max"])

mode = st.radio("Mode", ["Hybrid search", "RAG (template synthesis)"], horizontal=True)

if query:
    try:
        if mode.startswith("RAG"):
            response = requests.post(
                f"{API}/query",
                json={"q": query, "redact_level": redact},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            st.subheader("Answer")
            st.write(data.get("answer"))
            if data.get("warning"):
                st.info(data["warning"])
            if data.get("pii_warning"):
                st.warning(data["pii_warning"])
            st.subheader("Sources")
            for i, result in enumerate(data.get("sources") or [], 1):
                with st.expander(f"{i}. {(result.get('content') or '')[:80]}…"):
                    st.markdown(f"**Role:** {result.get('role')}")
                    st.markdown(f"**Platform:** {result.get('source_platform')}")
                    st.markdown(f"**Timestamp:** {result.get('timestamp')}")
                    st.markdown(f"**Export:** {result.get('export_file')}")
                    st.markdown(f"**Method:** {result.get('retrieval_method')}")
                    st.markdown("---")
                    st.markdown(result.get("content") or "")
        else:
            response = requests.get(
                f"{API}/search",
                params={"q": query, "k": top_k, "redact_level": redact},
                timeout=30,
            )
            response.raise_for_status()
            search_data = response.json()
            st.session_state.search_id = search_data.get("search_id")
            st.caption(
                f"BM25 hits: {search_data.get('bm25_hits')} · "
                f"Vector: {search_data.get('vector_status')} "
                f"({search_data.get('vector_hits')} hits) · "
                f"{search_data.get('total_latency_ms', 0):.0f} ms"
            )
            for i, result in enumerate(search_data.get("results") or [], 1):
                preview = (result.get("content") or "")[:80]
                score = result.get("combined_score") or result.get("relevance_score") or 0
                with st.expander(f"{i}. {preview}…  (score {score:.4f})"):
                    st.markdown(f"**Role:** {result.get('role')}")
                    st.markdown(f"**Platform:** {result.get('source_platform')}")
                    st.markdown(f"**Timestamp:** {result.get('timestamp')}")
                    st.markdown(f"**Export:** {result.get('export_file')}")
                    st.markdown(f"**Method:** {result.get('retrieval_method')}")
                    if result.get("pii_redacted"):
                        st.caption(f"PII redacted: {result.get('pii_fields_redacted')}")
                    st.markdown("---")
                    st.markdown(result.get("content") or "")
    except Exception as exc:
        st.error(f"Search failed: {exc}")

try:
    health = requests.get(f"{API}/health", timeout=2).json()
    st.sidebar.caption(f"API {health.get('status')} · local_only={health.get('local_only')}")
except Exception:
    st.sidebar.error(f"API unreachable at {API}")
