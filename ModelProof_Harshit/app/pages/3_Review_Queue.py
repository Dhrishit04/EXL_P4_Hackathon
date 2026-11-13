from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import ARTIFACTS, IS_FIXTURE  # noqa: E402

st.set_page_config(page_title="Review queue | ModelProof", layout="wide")
if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")
st.title("Human review queue")

graph = None
try:
    from modelproof import config, graph
    config.ARTIFACTS = ARTIFACTS
except ImportError:
    pass

checkpoint_file = ARTIFACTS / "checkpoints.sqlite"
if graph is not None and checkpoint_file.is_file():
    pending = graph.pending_gates()
    if not pending:
        st.info("No pending review gates.")
    for gate in pending:
        with st.container(border=True):
            st.subheader(f"{gate['model_id']} — {gate['gate']}")
            st.write(gate.get("summary", ""))
            with st.form(f"gate-{gate['thread_id']}"):
                reviewer = st.text_input("Reviewer", key=f"reviewer-{gate['thread_id']}")
                comment = st.text_area("Review comment", key=f"comment-{gate['thread_id']}")
                approve, reject = st.columns(2)
                approved = approve.form_submit_button("Approve")
                rejected = reject.form_submit_button("Reject")
                if approved or rejected:
                    if not reviewer.strip():
                        st.error("Enter a reviewer name before recording a decision.")
                    else:
                        graph.resume(
                            gate["thread_id"],
                            "approve" if approved else "reject",
                            comment,
                            reviewer.strip(),
                        )
                        st.success("Decision recorded.")
                        st.rerun()
else:
    st.info("Approvals run locally; this is the read only demo.")
    audit_path = ARTIFACTS / "audit" / "audit_log.jsonl"
    if audit_path.is_file():
        approvals = []
        with audit_path.open(encoding="utf-8") as audit_file:
            for line in audit_file:
                event = json.loads(line)
                event_name = str(event.get("event", "")).lower()
                if event_name in {"approval", "gate_approved", "gate_rejected"} or "approval" in event_name:
                    approvals.append(event)
        if approvals:
            st.dataframe(approvals, use_container_width=True, hide_index=True)
        else:
            st.caption("No approval events are recorded.")
