from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from app._data import IS_FIXTURE, read_json  # noqa: E402

st.set_page_config(page_title="Business case | ModelProof", layout="wide")
if IS_FIXTURE:
    st.error("FIXTURE DATA — all displayed values are synthetic examples, not results.")
st.title("Business case")
st.caption("All slider values are assumptions; outputs are scenario estimates, not measured savings.")

left, right = st.columns(2)
with left:
    models = st.slider("Models in estate (assumption)", min_value=1, max_value=500, value=250)
    validations = st.slider(
        "Validations per model per year (assumption)",
        min_value=0.1,
        max_value=5.0,
        value=1.0,
        step=0.1,
    )
    weeks = st.slider("Weeks per validation (assumption)", min_value=8, max_value=12, value=10)
with right:
    automated_share = st.slider("Validator effort automated (assumption)", min_value=0, max_value=100, value=40)
    weekly_cost = st.slider(
        "Cost per validator week (assumption, £)",
        min_value=0,
        max_value=10000,
        value=1500,
        step=100,
    )

annual_weeks = models * validations * weeks
saved_weeks = annual_weeks * automated_share / 100
saved_cost = saved_weeks * weekly_cost
st.subheader("Scenario estimate")
kpis = st.columns(3)
kpis[0].metric("Annual validator weeks", f"{annual_weeks:,.1f}")
kpis[1].metric("Weeks saved", f"{saved_weeks:,.1f}")
kpis[2].metric("Estimated cost saved", f"£{saved_cost:,.0f}")
st.write(
    "Formula: models × validations per model per year × weeks per validation "
    "gives annual validator weeks. Multiply by the assumed automated share for "
    "weeks saved, then by cost per validator week for estimated cost saved."
)

metrics = read_json("metrics.json") or {}
st.subheader("Measured project metrics")
runtime = metrics.get("runtime_per_model_seconds", metrics.get("runtime_seconds_per_model"))
grounding = metrics.get("grounding_score")
measured = st.columns(2)
measurement_label = "FIXTURE (not measured)" if IS_FIXTURE else "measured"
measured[0].metric(
    f"Runtime per model ({measurement_label})",
    f"{runtime} s" if runtime is not None else "Not available",
)
measured[1].metric(
    f"Grounding score ({measurement_label})",
    grounding if grounding is not None else "Not available",
)
