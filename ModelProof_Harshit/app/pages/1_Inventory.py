from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import IS_FIXTURE, dataframe, load_inventory  # noqa: E402

st.set_page_config(page_title="Inventory | ModelProof", layout="wide")
if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")
st.title("Model inventory")

records = load_inventory()
if not records:
    st.info("No inventory records found.")
    st.stop()

df = dataframe(records)
filters = st.columns(4)
choices = {
    "risk_tier": sorted(df["risk_tier"].dropna().unique().tolist()) if "risk_tier" in df else [],
    "status": sorted(df["status"].dropna().unique().tolist()) if "status" in df else [],
    "platform_language": sorted(df["platform_language"].dropna().unique().tolist()) if "platform_language" in df else [],
    "documentation_status": sorted(df["documentation_status"].dropna().unique().tolist()) if "documentation_status" in df else [],
}
selected = {}
for column, (key, values) in zip(filters, choices.items()):
    selected[key] = column.multiselect(key.replace("_", " ").title(), values)
filtered = df
for key, values in selected.items():
    if values and key in filtered:
        filtered = filtered[filtered[key].isin(values)]

st.download_button(
    "Download filtered inventory CSV",
    filtered.to_csv(index=False).encode("utf-8"),
    file_name="modelproof_inventory.csv",
    mime="text/csv",
)
st.dataframe(filtered, use_container_width=True, hide_index=True)
st.subheader("Model records")
for record in records:
    with st.expander(f"{record.get('model_id', 'Unknown')} — {record.get('name', 'Model')}"):
        for finding in record.get("security_flags", []):
            st.warning(f"{finding.get('severity', 'flag').upper()}: {finding.get('description', 'Security finding')}")
        st.json(record)
