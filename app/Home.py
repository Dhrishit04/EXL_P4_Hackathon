from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import IS_FIXTURE, load_inventory, model_artifact, model_ids  # noqa: E402

st.set_page_config(page_title="ModelProof | Validator Workbench", page_icon="🛡️", layout="wide")

if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")

st.title("ModelProof Validator Workbench")
st.caption("Model risk validation with traceable evidence and human review.")

records = load_inventory()
ids = model_ids()
reports = {model_id: model_artifact(model_id, "validation_report.json") for model_id in ids}
certificates = {model_id: model_artifact(model_id, "parity_certificate.json") for model_id in ids}
monitoring = {model_id: model_artifact(model_id, "monitoring.json") for model_id in ids}

tiers: dict[str, int] = {}
for record in records:
    tier = str(record.get("risk_tier", "Unknown"))
    tiers[tier] = tiers.get(tier, 0) + 1
doc_status = {status: sum(row.get("documentation_status") == status for row in records)
              for status in ("current", "outdated", "missing")}
verified_drifts = sum(
    bool(drift.get("verified"))
    for record in records
    for drift in record.get("doc_code_drifts", [])
)
parity_passes = sum(cert.get("overall") == "PASS" for cert in certificates.values() if cert)
ratings = [report.get("rating") for report in reports.values() if report]
open_findings = sum(
    finding.get("status", "open") == "open"
    for report in reports.values() if report
    for finding in report.get("findings", [])
)
trigger_months = [
    result["trigger_month"] for result in monitoring.values()
    if result and result.get("trigger_month") is not None
]

tiles = st.columns(4)
tiles[0].metric("Models discovered", len(records))
tiles[1].metric("Risk tier mix", " · ".join(f"T{k}: {v}" for k, v in sorted(tiers.items())) or "—")
tiles[2].metric("Documentation status", " · ".join(f"{k}: {v}" for k, v in doc_status.items()))
tiles[3].metric("Verified drifts", verified_drifts)
tiles = st.columns(4)
tiles[0].metric("Parity certificates", f"{parity_passes} PASS / {sum(bool(v) for v in certificates.values())} total")
tiles[1].metric("Validation ratings", ", ".join(sorted(set(ratings))) or "—")
tiles[2].metric("Open findings", open_findings)
tiles[3].metric("Monitoring trigger month", ", ".join(map(str, trigger_months)) or "None")

st.subheader("Validation pipeline")
st.caption("A stage is shown as complete only when its corresponding artifact records that outcome.")
stages = ("Discover", "Document", "Redevelop", "Validate", "Monitor")
board = []
for record in records:
    model_id = record["model_id"]
    certificate = certificates.get(model_id)
    report = reports.get(model_id)
    monitor = monitoring.get(model_id)
    board.append({
        "Model": model_id,
        "Discover": "Complete",
        "Document": (
            "Complete"
            if record.get("status") in {"documented", "redeveloped", "validated", "monitored"}
            else "Pending"
        ),
        "Redevelop": certificate.get("overall") if certificate else "Not applicable",
        "Validate": report.get("rating") if report else "Pending",
        "Monitor": "Triggered" if monitor and monitor.get("trigger_month") is not None
        else ("Active" if monitor else "Pending"),
    })
if board:
    board_frame = pd.DataFrame(board)

    def stage_style(value: object) -> str:
        normalized = str(value).lower()
        if normalized in {"complete", "pass", "fit for use", "active"}:
            return "background-color: #E5F4EA; color: #176B35"
        if normalized in {"fail", "not fit"}:
            return "background-color: #FCE8E6; color: #A12622"
        if normalized in {"pending", "triggered", "fit with conditions"}:
            return "background-color: #FFF2D6; color: #805500"
        return ""

    styled_board = board_frame.style.map(stage_style, subset=list(stages))
    st.dataframe(styled_board, use_container_width=True, hide_index=True)
else:
    st.info("No inventory artifacts found. Select **Inventory** to check the artifact location.")

st.subheader("Quick navigation")
st.write("Use the pages in the sidebar to inspect inventory, model evidence, review gates, audit events, and the business-case assumptions.")
