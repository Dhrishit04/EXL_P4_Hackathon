from datetime import UTC, date, datetime

import pytest

from modelproof import schemas as s

NOW = datetime(2026, 11, 13, 17, 30, tzinfo=UTC)
EV = s.Evidence(id="E1", kind="code", path="a.sas", line_start=1, line_end=2, excerpt="x")
FINDING = s.Finding(
    id="F1", model_id="M", area="a", severity="high", ss123_principle="P1", description="d"
)
CLAIM = s.Claim(section="1 Purpose and use", text="t", evidence_ids=["E1"])
CHECK = s.CheckResult(test="gini", area="discrimination", value=0.5, threshold=">=0.4", rag="green")
RESULTS = s.ValidationResults(model_id="M", tests=[CHECK], tables={"t": [{"a": 1}]})
DRIFT = s.Drift(field="f", doc_value="1", code_value="2", doc_evidence_id="D", code_evidence_id="C")

INSTANCES = [
    EV,
    s.Facts(
        model_id="M",
        language="SAS",
        files=[{"path": "a", "sha256": "h", "n_lines": 1, "kind": "code"}],
        evidence=[EV],
    ),
    s.Feature(name="x", evidence_id="E1"),
    DRIFT,
    FINDING,
    s.Approval(gate="discovery", decision="approve", reviewer="r", ts=NOW),
    s.InventoryRecord(
        model_id="M",
        name="n",
        model_type="PD",
        platform_language="SAS",
        materiality="H",
        complexity="L",
        risk_tier=1,
        documentation_status="current",
        doc_code_drifts=[DRIFT],
        security_flags=[FINDING],
        last_validated=date(2026, 1, 1),
        features=[s.Feature(name="x")],
        approvals=[s.Approval(gate="override", decision="reject", reviewer="r", ts=NOW, auto=True)],
    ),
    CLAIM,
    s.Documentation(
        model_id="M", claims=[CLAIM], grounding_score=1.0, drifts=[DRIFT], generated_at=NOW
    ),
    s.ParityLevel(level="L1", name="n", passed=True, metric="m", value=0.0, tolerance=1e-12),
    s.ParityCertificate(
        model_id="M",
        overall="PASS",
        hashes={"a": "b"},
        versions={"python": "3.11"},
        attempt=1,
        run_id="r",
        created_at=NOW,
        levels=[
            s.ParityLevel(level="L5", name="n", passed=True, metric="m", value=0.0, tolerance=1e-9)
        ],
    ),
    CHECK,
    RESULTS,
    s.ValidationReport(
        model_id="M",
        results=RESULTS,
        narrative={"a": "b"},
        findings=[FINDING],
        rating="Fit with conditions",
        claims=[CLAIM],
        created_at=NOW,
    ),
    s.MonitoringPoint(
        month=1,
        score_psi=0.1,
        csi={"x": 0.1},
        gini=0.5,
        observed_dr=0.2,
        expected_dr=0.2,
        jeffreys_failures=0,
    ),
    s.MonitoringResult(
        model_id="M",
        trigger_month=None,
        points=[
            s.MonitoringPoint(
                month=1,
                score_psi=0.1,
                csi={},
                gini=0.5,
                observed_dr=0.2,
                expected_dr=0.2,
                jeffreys_failures=0,
                breaches=["psi"],
            )
        ],
    ),
]


@pytest.mark.parametrize("obj", INSTANCES, ids=lambda o: type(o).__name__)
def test_json_round_trip(obj):
    assert type(obj).model_validate_json(obj.model_dump_json()) == obj


def test_every_schema_is_covered():
    models = {v for v in vars(s).values() if isinstance(v, type) and issubclass(v, s.BaseModel)} - {
        s.BaseModel
    }
    assert models == {type(o) for o in INSTANCES}
