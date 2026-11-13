from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import ARTIFACTS, IS_FIXTURE  # noqa: E402

st.set_page_config(page_title="Audit log | ModelProof", layout="wide")
if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")
st.title("Audit log")

verified = None
try:
    from modelproof import audit, config
    config.ARTIFACTS = ARTIFACTS
except ImportError:
    audit = None
if audit is not None:
    verified = audit.verify_chain()
else:
    verified = False
if verified:
    st.success("Audit chain verified")
else:
    st.warning("Audit chain could not be verified by the runtime audit module.")

path = ARTIFACTS / "audit" / "audit_log.jsonl"
events = []
if path.is_file():
    with path.open(encoding="utf-8") as audit_file:
        events = [json.loads(line) for line in audit_file if line.strip()]
if not events:
    st.info("No audit events found.")
    st.stop()

df = pd.DataFrame(events)
cols = st.columns(2)
models = sorted(df["model_id"].dropna().unique().tolist()) if "model_id" in df else []
event_types = sorted(df["event"].dropna().unique().tolist()) if "event" in df else []
model_filter = cols[0].multiselect("Model", models)
event_filter = cols[1].multiselect("Event type", event_types)
if model_filter and "model_id" in df:
    df = df[df["model_id"].isin(model_filter)]
if event_filter and "event" in df:
    df = df[df["event"].isin(event_filter)]
st.dataframe(df, use_container_width=True, hide_index=True)
