import sys
import types
from datetime import date

import pandas as pd
import pytest

import modelproof
from modelproof import audit, config, inventory, llm
from modelproof.agents import validate
from modelproof.schemas import (
    CheckResult,
    Claim,
    Facts,
    Feature,
    InventoryRecord,
    ValidationReport,
    ValidationResults,
)

DEV = pd.DataFrame({"ID": [1, 2], "DEFAULT": [0, 1], "LIMIT_BAL": [10, 20], "AGE": [30, 40]})
TESTS = [
    CheckResult(test="gini", area="discrimination", value=0.52, threshold=">= 0.40", rag="green", details={"n": 100}),
    CheckResult(test="score_psi", area="stability", value=0.31, threshold="< 0.25", rag="red", details={"bins": 10, "per_bin": list(range(20))}),
]  # fmt: skip
RESULTS = ValidationResults(
    model_id="CR-PD-002",
    tests=TESTS,
    tables={"calibration": [{"grade": g, "n": 5} for g in "ABCDEFG"]},
)
NARRATIVE = validate._Narrative(
    sections=[
        validate._Section(area="discrimination", text="The Gini is 0.52. It is above the 0.40 threshold."),
        validate._Section(area="stability", text="The score PSI is 0.31, which is red."),
        validate._Section(area="bogus", text="Not an area in the results."),
    ],
    findings=[
        validate._Finding(area="stability", severity="high", ss123_principle="P4", description="PSI of 0.31 breaches the limit.", evidence_ids=["score_psi", "invented"], recommendation="Recalibrate."),
    ],
)  # fmt: skip


def fake_module(monkeypatch, name, **attrs):
    mod = types.ModuleType(f"modelproof.{name}")
    mod.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, f"modelproof.{name}", mod)
    monkeypatch.setattr(modelproof, name, mod, raising=False)
    return mod


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    seen = {"verify": {}, "run_suite": {}, "llm": {}}

    def run_suite(model_id, dev, holdout, fn, features):
        seen["run_suite"] = {"model_id": model_id, "features": features, "fn": fn}
        return RESULTS

    def verify(claims, facts, metrics=None):
        seen["verify"] = {"claims": claims, "facts": facts, "metrics": metrics}
        out = [
            c.model_copy(update={"status": "supported" if c.evidence_ids else "unsupported"})
            for c in claims
        ]
        return out, sum(c.status == "supported" for c in out) / len(out)

    def structured(system, user, schema, task):
        seen["llm"] = {"system": system, "user": user, "schema": schema, "task": task}
        return NARRATIVE

    fake_module(monkeypatch, "data", load_cr_pd_002=lambda split: DEV)
    fake_module(monkeypatch, "parity", score_fn=lambda path: lambda df: df)
    fake_module(
        monkeypatch, "validation", run_suite=run_suite, rating=lambda tests: "Fit with conditions"
    )
    fake_module(
        monkeypatch, "extract", facts_for=lambda m: Facts(model_id=m, language="R", files=[])
    )
    fake = types.ModuleType("modelproof.agents.verify")
    fake.verify = verify
    monkeypatch.setitem(sys.modules, "modelproof.agents.verify", fake)
    monkeypatch.setattr(modelproof.agents, "verify", fake, raising=False)
    monkeypatch.setitem(sys.modules, "modelproof.report", None)  # WP3 renderer missing by default
    monkeypatch.setattr(llm, "structured", structured)
    return types.SimpleNamespace(seen=seen, path=tmp_path)


def test_validate_end_to_end(env):
    rep = validate.run("CR-PD-002")
    # rating comes from validation.rating, not the LLM
    assert rep.rating == "Fit with conditions" and rep.results == RESULTS
    # narrative only for areas present in the results
    assert set(rep.narrative) == {"discrimination", "stability"}
    f = rep.findings[0]
    assert (f.id, f.model_id, f.status, f.severity, f.ss123_principle) == (
        "VF-1",
        "CR-PD-002",
        "open",
        "high",
        "P4",
    )
    assert f.evidence_ids == ["score_psi"]  # invented ids dropped
    # persisted, valid, and the render failure did not crash it
    path = env.path / "CR-PD-002" / "validation_report.json"
    assert ValidationReport.model_validate_json(path.read_text()) == rep
    events = [e["event"] for e in audit.read()]
    assert events == ["validate.render_skipped", "validate.completed"] and audit.verify_chain()
    done = audit.read()[-1]
    assert done["payload"]["rating"] == "Fit with conditions" and done["payload"]["n_findings"] == 1


def test_llm_sees_results_only_and_guarded(env):
    validate.run("CR-PD-002", reviewer_comment="Be explicit about PSI.")
    c = env.seen["llm"]
    assert (
        c["task"] == "validate"
        and c["schema"] is validate._Narrative
        and "untrusted_source" in c["system"]
    )
    assert '"test": "gini"' in c["user"] and '"rag": "red"' in c["user"]
    assert "per_bin" not in c["user"]  # large detail arrays are dropped
    assert (
        '"n_rows": 7' in c["user"] and '"grade": "F"' not in c["user"]
    )  # tables truncated to the head
    assert "Be explicit about PSI." in c["user"]
    assert "LIMIT_BAL" not in c["user"]  # no data columns/rows


def test_claims_and_metrics_passed_to_verify(env):
    rep = validate.run("CR-PD-002")
    v = env.seen["verify"]
    assert v["facts"].model_id == "CR-PD-002"
    texts = [(c.section, c.text) for c in v["claims"]]
    assert texts[:3] == [
        ("discrimination", "The Gini is 0.52."),
        ("discrimination", "It is above the 0.40 threshold."),
        ("stability", "The score PSI is 0.31, which is red."),
    ]
    assert v["claims"][0].evidence_ids == ["gini"] and v["claims"][2].evidence_ids == ["score_psi"]
    assert v["claims"][-1].section == "findings" and v["claims"][-1].evidence_ids == ["score_psi"]
    assert not any(c.section == "bogus" for c in v["claims"])
    m = v["metrics"]
    assert m["gini"]["value"] == 0.52 and m["gini"]["n"] == 100 and m["gini"]["threshold_0"] == 0.4
    assert (
        m["score_psi"]["bins"] == 10
        and m["score_psi"]["threshold_0"] == 0.25
        and "per_bin" not in m["score_psi"]
    )
    assert all(isinstance(c, Claim) for c in rep.claims) and len(rep.claims) == len(v["claims"])


def test_features_from_inventory_else_raw_columns(env):
    validate.run("CR-PD-002")
    assert env.seen["run_suite"]["features"] == [
        "LIMIT_BAL",
        "AGE",
    ]  # raw columns minus ID and DEFAULT
    rec = InventoryRecord(
        model_id="CR-PD-002", name="n", model_type="PD", platform_language="R", materiality="H", complexity="M",
        risk_tier=1, documentation_status="current", last_validated=date(2026, 1, 1),
        features=[Feature(name="AGE"), Feature(name="woe_pay_0")],
    )  # fmt: skip
    inventory.upsert(rec)
    validate.run("CR-PD-002")
    assert env.seen["run_suite"]["features"] == ["AGE"]  # only names that are real columns


def test_render_called_when_available(env, monkeypatch):
    calls = []
    pkg = types.ModuleType("modelproof.report")
    render = types.ModuleType("modelproof.report.render")
    render.validation = calls.append
    pkg.render = render
    pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "modelproof.report", pkg)
    monkeypatch.setitem(sys.modules, "modelproof.report.render", render)
    validate.run("CR-PD-002")
    assert calls == ["CR-PD-002"]
    assert [e["event"] for e in audit.read()] == ["validate.completed"]


def test_real_verify_integration(env, monkeypatch):
    real = pytest.importorskip("modelproof.agents.verify")
    monkeypatch.setitem(sys.modules, "modelproof.agents.verify", real)
    monkeypatch.setattr(modelproof.agents, "verify", real, raising=False)
    rep = validate.run("CR-PD-002")
    by_text = {c.text: c for c in rep.claims}
    assert by_text["The Gini is 0.52."].status == "supported"
    assert by_text["The score PSI is 0.31, which is red."].status == "supported"
