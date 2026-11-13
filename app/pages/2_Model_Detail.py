from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import (  # noqa: E402
    ARTIFACTS,
    IS_FIXTURE,
    dataframe,
    model_artifact,
    model_ids,
    model_record,
    read_json,
)

try:
    from modelproof.report import charts as report_charts
except ImportError:
    report_charts = None

st.set_page_config(page_title="Model detail | ModelProof", layout="wide")
if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")
st.title("Model detail")


def show_validation_chart(name: str, chart: dict) -> bool:
    if report_charts is not None:
        if name == "roc":
            figure = report_charts.roc(chart["fpr"], chart["tpr"])
        elif name == "ks":
            figure = report_charts.ks(chart["score"], chart["good_cdf"], chart["bad_cdf"])
        elif name == "score_distribution":
            figure = report_charts.score_histogram(chart["edges"], chart["dev"], chart["holdout"])
        elif name == "calibration":
            records = chart["records"]
            figure = report_charts.calibration(
                [row["mean_predicted"] for row in records],
                [row["observed_rate"] for row in records],
            )
        else:
            return False
        st.pyplot(figure)
        return True

    if name == "roc":
        st.line_chart(pd.DataFrame({"False positive rate": chart["fpr"], "True positive rate": chart["tpr"]}))
    elif name == "ks":
        st.line_chart(pd.DataFrame({
            "Score": chart["score"],
            "Non-default": chart["good_cdf"],
            "Default": chart["bad_cdf"],
        }).set_index("Score"))
    elif name == "score_distribution":
        edges = chart["edges"]
        st.bar_chart(pd.DataFrame({
            "Score range": [f"{edges[i]}–{edges[i + 1]}" for i in range(len(edges) - 1)],
            "Development": chart["dev"],
            "Holdout": chart["holdout"],
        }).set_index("Score range"))
    elif name == "calibration":
        records = chart["records"]
        st.line_chart(pd.DataFrame({
            "Predicted": [row["mean_predicted"] for row in records],
            "Observed": [row["observed_rate"] for row in records],
        }))
    else:
        return False
    return True


ids = model_ids()
if not ids:
    st.info("No model artifacts found.")
    st.stop()
model_id = st.selectbox("Select a model", ids)
record = model_record(model_id) or {}
documentation = model_artifact(model_id, "documentation.json", "Documentation") or {}
certificate = model_artifact(model_id, "parity_certificate.json", "ParityCertificate") or {}
validation = model_artifact(model_id, "validation_results.json", "ValidationResults") or {}
report = model_artifact(model_id, "validation_report.json", "ValidationReport") or {}
monitoring = model_artifact(model_id, "monitoring.json", "MonitoringResult") or {}

documentation_tab, redevelopment_tab, validation_tab, monitoring_tab = st.tabs(
    ["Documentation", "Redevelopment", "Validation", "Monitoring"]
)
with documentation_tab:
    st.metric("Grounding score", documentation.get("grounding_score", "—"))
    claims = documentation.get("claims", [])
    facts = model_artifact(model_id, "facts.json", "Facts") or {}
    evidence_by_id = {item.get("id"): item for item in facts.get("evidence", [])}
    sections = sorted({claim.get("section", "Other") for claim in claims})
    for section in sections:
        st.markdown(f"#### {section}")
        for claim in (item for item in claims if item.get("section", "Other") == section):
            if claim.get("status") != "supported":
                st.warning(f"{claim.get('status', 'unsupported').title()}: {claim.get('text', 'Claim')}")
            else:
                st.write(claim.get("text", ""))
            st.caption(claim.get("reason", ""))
            for evidence_id in claim.get("evidence_ids", []):
                evidence = evidence_by_id.get(evidence_id)
                if evidence:
                    with st.expander(f"{evidence['path']}:{evidence['line_start']}–{evidence['line_end']}"):
                        st.code(evidence.get("excerpt", ""))
    drifts = record.get("doc_code_drifts", documentation.get("drifts", []))
    st.markdown("#### Documentation/code drift")
    if drifts:
        drift_rows = []
        for drift in drifts:
            doc_evidence = evidence_by_id.get(drift.get("doc_evidence_id"), {})
            code_evidence = evidence_by_id.get(drift.get("code_evidence_id"), {})
            drift_rows.append({
                "Field": drift.get("field"),
                "Documented value": drift.get("doc_value"),
                "Document line": f"{doc_evidence.get('path', '—')}:{doc_evidence.get('line_start', '—')}",
                "Code value": drift.get("code_value"),
                "Code line": f"{code_evidence.get('path', '—')}:{code_evidence.get('line_start', '—')}",
                "Verified": drift.get("verified"),
            })
        st.dataframe(dataframe(drift_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No drift records.")

with redevelopment_tab:
    attempts = read_json(f"{model_id}/redevelop/attempts.json") or []
    for attempt in attempts:
        st.markdown(f"**Attempt {attempt.get('attempt', '?')} — {attempt.get('overall', 'Unknown')}**")
        st.caption(attempt.get("localiser_summary", ""))
        st.write("Passed parity levels:", ", ".join(attempt.get("passed_levels", [])) or "None")
    levels = certificate.get("levels", [])
    if levels:
        st.dataframe(dataframe(levels), use_container_width=True, hide_index=True)
        st.write("Hashes")
        st.json(certificate.get("hashes", {}))
    elif not attempts:
        st.info("No redevelopment artifacts for this model.")

with validation_tab:
    rating = report.get("rating")
    if rating:
        if rating == "Not fit":
            st.error(f"Validation rating: {rating}")
        elif rating == "Fit with conditions":
            st.warning(f"Validation rating: {rating}")
        else:
            st.success(f"Validation rating: {rating}")
    tests = validation.get("tests", [])
    if tests:
        for area in sorted({item.get("area", "other") for item in tests}):
            st.markdown(f"#### {area.replace('_', ' ').title()}")
            area_frame = dataframe([item for item in tests if item.get("area", "other") == area])

            def rag_style(value: object) -> str:
                colors = {
                    "green": "background-color: #E5F4EA; color: #176B35",
                    "amber": "background-color: #FFF2D6; color: #805500",
                    "red": "background-color: #FCE8E6; color: #A12622",
                }
                return colors.get(str(value).lower(), "")

            styled_frame = area_frame.style.map(rag_style, subset=["rag"]) if "rag" in area_frame else area_frame
            st.dataframe(styled_frame, use_container_width=True, hide_index=True)
    charts = validation.get("charts", {})
    if charts:
        for name, chart in charts.items():
            st.markdown(f"#### {name.replace('_', ' ').title()}")
            if not show_validation_chart(name, chart):
                st.caption(f"Chart format not recognized: {name}")
    fairness_rows = validation.get("tables", {}).get("fairness", [])
    if fairness_rows and report_charts is not None:
        for sensitive in sorted({row.get("sensitive", "Group") for row in fairness_rows}):
            rows = [
                row for row in fairness_rows
                if row.get("sensitive", "Group") == sensitive and row.get("approval_rate") is not None
            ]
            if rows:
                st.pyplot(report_charts.fairness(
                    [row["group"] for row in rows],
                    [row["approval_rate"] for row in rows],
                    metric=f"{sensitive} approval rate",
                ))
    if tests and report_charts is not None:
        st.pyplot(report_charts.rag_summary(tests))
    findings = report.get("findings", [])
    for finding in findings:
        severity = finding.get("severity", "low")
        message = f"{severity.upper()}: {finding.get('description', '')}"
        (st.error if severity == "high" else st.warning if severity == "medium" else st.info)(message)
    html_path = ARTIFACTS / model_id / "validation_report.html"
    if html_path.is_file():
        st.download_button(
            "Download validation HTML report",
            data=html_path.read_bytes(),
            file_name=f"{model_id}_validation_report.html",
            mime="text/html",
        )
    elif not tests and not rating:
        st.info("No validation artifacts for this model.")

with monitoring_tab:
    st.caption("Simulated drift" if monitoring.get("simulated", True) else "Monitoring results")
    points = monitoring.get("points", [])
    if points:
        monitor_df = dataframe(points)
        if "month" in monitor_df and "score_psi" in monitor_df:
            if report_charts is not None:
                st.pyplot(report_charts.psi_by_month(
                    monitor_df["month"].tolist(),
                    monitor_df["score_psi"].tolist(),
                    trigger_month=monitoring.get("trigger_month"),
                ))
            else:
                monitor_df = monitor_df.set_index("month")
                monitor_df["Green threshold (0.10)"] = 0.10
                monitor_df["Amber threshold (0.25)"] = 0.25
                trigger_month = monitoring.get("trigger_month")
                if trigger_month is not None:
                    monitor_df["Trigger month"] = [
                        monitor_df.loc[month, "score_psi"] if month == trigger_month else None
                        for month in monitor_df.index
                    ]
                st.line_chart(monitor_df[[column for column in (
                    "score_psi", "Green threshold (0.10)", "Amber threshold (0.25)", "Trigger month"
                ) if column in monitor_df]])
        csi_rows = [
            {"month": point.get("month"), "field": field, "csi": value}
            for point in points for field, value in point.get("csi", {}).items()
        ]
        if csi_rows:
            st.dataframe(dataframe(csi_rows), use_container_width=True, hide_index=True)
        if monitoring.get("trigger_month") is not None:
            st.warning(f"Revalidation trigger at month {monitoring['trigger_month']}.")
    else:
        st.info("No monitoring artifact for this model.")
