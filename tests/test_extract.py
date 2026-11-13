from pathlib import Path

import pytest
import yaml

from modelproof import config, extract, security

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"
INV = yaml.safe_load((GOLD / "inventory_gold.yaml").read_text())
RISKS = yaml.safe_load((GOLD / "seeded_risks.yaml").read_text())
DRIFTS = yaml.safe_load((GOLD / "seeded_drifts.yaml").read_text())
PARAMS = {  # code side of the seeded drifts that are named constants
    "CR-PD-001": {"CUTOFF": "540", "PDO": "20", "BASE_ODDS": "30", "dev_sample_share": "0.7", "grade_A_min": "590"},
    "CR-PD-002": {"CUTOFF": "560", "PDO": "20", "BASE_ODDS": "25", "BASE_SCORE": "600"},
    "FR-TX-003": {"random_state": "42", "max_iter": "200"},
    "PR-RB-004": {"BASE_RATE": "0.045"},
}
COMMENTS = {"CR-PD-001": ("CUTOFF", "520"), "CR-PD-002": ("PDO", "25"), "PR-RB-004": ("BASE_RATE", "4.0")}


@pytest.fixture(autouse=True)
def tmp_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELPROOF_ARTIFACTS", str(tmp_path))
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)


@pytest.mark.parametrize("mid", INV)
def test_facts_match_gold_inventory_and_dead_variables(mid, tmp_path):
    f = extract.facts_for(mid)
    assert f.language == INV[mid]["language"] and f.target == INV[mid]["target"]
    assert set(f.dead_variables) == {r["description"].split()[0] for r in RISKS if r["kind"] == "dead_variable" and r["model_id"] == mid}
    assert f.dependencies == INV[mid]["upstream_models"]
    assert (tmp_path / mid / "facts.json").exists()
    assert not any("SCENARIO" in x["path"] or "golden" in x["path"] for x in f.files)


@pytest.mark.parametrize("mid", INV)
def test_parameters_have_evidence_with_the_value(mid):
    f = extract.facts_for(mid)
    ev = {e.id: e for e in f.evidence}
    for name, val in PARAMS[mid].items():
        p = f.parameters[name]
        assert p["value"] == val and val in ev[p["evidence_id"]].excerpt, name
        assert ev[p["evidence_id"]].sha256 and ev[p["evidence_id"]].kind == "code"


@pytest.mark.parametrize(("mid", "name_value"), COMMENTS.items())
def test_stale_comment_value_is_recorded_next_to_the_constant(mid, name_value):
    name, stale = name_value
    assert extract.facts_for(mid).parameters[f"{name}_comment"]["value"] == stale


def test_model_calls_and_old_docs_are_evidence():
    r, sas, py = (extract.facts_for(m) for m in ("CR-PD-002", "CR-PD-001", "FR-TX-003"))
    glm = next(c for c in r.model_calls if c["kind"] == "glm")["text"]
    assert "woe_util" in glm and "EDUCATION" not in glm
    assert "w_pstat" in next(c for c in sas.model_calls if c["kind"] == "PROC LOGISTIC")["text"]
    assert py.model_calls[0]["text"].startswith("HistGradientBoostingClassifier")
    assert "PR-RB-004" not in r.dependencies
    for d in DRIFTS:  # every planted doc line is citable
        ev = [e for e in extract.facts_for(d["model_id"]).evidence if e.kind == "doc" and e.path == d["doc_file"] and e.line_start == d["doc_line"]]
        assert ev and d["doc_anchor"] in ev[0].excerpt, d["id"]


def test_scanner_finds_only_the_seeded_injection():
    hits = security.scan("PR-RB-004")
    inj = next(r for r in RISKS if r["kind"] == "prompt_injection")
    assert len(hits) == 1 and hits[0].severity == "high" and hits[0].ss123_principle == "P2"
    assert hits[0].evidence_ids == [extract.evidence_id("PR-RB-004", Path(inj["file"]).name, inj["line"], inj["line"])]
    assert all(security.scan(m) == [] for m in ("CR-PD-001", "CR-PD-002", "FR-TX-003"))
    assert any(e.id == hits[0].evidence_ids[0] for e in extract.facts_for("PR-RB-004").evidence)


@pytest.mark.parametrize(("mid", "needle"), [("CR-PD-001", "ROUND("), ("CR-PD-002", "round(")])
def test_rounding_semantics_are_recorded_with_evidence(mid, needle):
    f = extract.facts_for(mid)
    ev = next(e for e in f.evidence if e.id == f.parameters["rounding"]["evidence_id"])
    assert needle in ev.excerpt and "half" in f.parameters["rounding"]["value"]
