import importlib.util
import json

import pytest
import yaml

from modelproof import audit, config, inventory
from modelproof.schemas import Drift, Finding, InventoryRecord

SPEC = importlib.util.spec_from_file_location("benchmark", config.ROOT / "scripts" / "benchmark.py")
bm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bm)


def rec(mid, **kw):
    base = dict(model_id=mid, name=mid, model_type="PD", platform_language="SAS", materiality="H",
                complexity="M", risk_tier=1, documentation_status="outdated")  # fmt: skip
    return InventoryRecord(**{**base, **kw})


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))


@pytest.fixture
def world(tmp_path, monkeypatch):
    art, gold = tmp_path / "artifacts", tmp_path / "gold"
    monkeypatch.setattr(config, "ARTIFACTS", art)
    monkeypatch.setattr(config, "GOLD_DIR", gold)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    drift = Drift(
        field="cutoff",
        doc_value="0.5",
        code_value="0.6",
        doc_evidence_id="d",
        code_evidence_id="c",
        verified=True,
    )
    bogus = Drift(
        field="x",
        doc_value="a",
        code_value="b",
        doc_evidence_id="x",
        code_evidence_id="y",
        verified=True,
    )
    flag = Finding(id="SEC-1", model_id="CR-PD-001", area="fairness", severity="high", ss123_principle="P3",
                   description="rbp.sas line 1: personal_status is a proxy for sex")  # fmt: skip
    inventory.upsert(
        rec(
            "CR-PD-001",
            doc_code_drifts=[drift, bogus],
            security_flags=[flag],
            downstream_models=["PR-RB-004"],
            target_definition="bad = 1",
            features=[{"name": "age"}, {"name": "personal_status"}],
        )
    )
    inventory.upsert(
        rec(
            "PR-RB-004",
            upstream_models=["CR-PD-001"],
            platform_language="SAS",
            documentation_status="missing",
        )
    )
    write(gold / "inventory_gold.yaml", yaml.dump({
        "CR-PD-001": {"language": "sas", "downstream_models": ["PR-RB-004"], "upstream_models": ["X"],
                      "model_type": "PD", "risk_tier": 1, "target": "bad", "features": ["personal_status", "age"]}}))  # fmt: skip
    write(gold / "seeded_drifts.yaml", yaml.dump([
        {"id": "D1", "model_id": "CR-PD-001", "field": "cutoff", "doc_file": "d.md", "doc_line": 3, "doc_value": "0.5",
         "code_file": "c.sas", "code_line": 7, "true_value": "0.6"},
        {"id": "D2", "model_id": "CR-PD-001", "field": "other", "doc_file": "d.md", "doc_line": 9, "doc_value": "9",
         "code_file": "c.sas", "code_line": 20, "true_value": "10"}]))  # fmt: skip

    def risk(i, m, k, d, **kw):
        return {
            "id": i,
            "model_id": m,
            "kind": k,
            "description": d,
            "file": "x/rbp.sas",
            "line": 1,
            "anchor": "a",
            **kw,
        }

    write(gold / "seeded_risks.yaml", yaml.dump([
        risk("R1", "CR-PD-001", "proxy_variable", "personal_status (sex proxy) is a predictor"),
        risk("R2", "PR-RB-004", "dependency", "reads the grade dataset written by CR-PD-001"),
        risk("R3", "PR-RB-004", "prompt_injection", "hidden instruction"),
        risk("R4", "CR-PD-001", "dead_variable", "debt_ratio is computed and never used"),
        risk("R5", "CR-PD-001", "stale_comment", "comment says 520", anchor="cutoff 520 per Committee"),
        risk("R6", "PR-RB-004", "undocumented_model", "no document")]))  # fmt: skip
    write(art / "CR-PD-001" / "facts.json", {"dead_variables": ["debt_ratio"], "parameters": {"CUTOFF": {}, "CUTOFF_comment": {}},
          "evidence": [{"id": "d", "path": "d.md", "line_start": 3, "line_end": 3}, {"id": "c", "path": "c.sas", "line_start": 7, "line_end": 8}]})  # fmt: skip

    def u(hit, mid, i, o, c):
        return {
            "task": "t",
            "input_tokens": i,
            "output_tokens": o,
            "cost_usd": c,
            "cache_hit": hit,
            "model_id": mid,
        }

    write(
        art / "runs" / "live-1" / "llm_usage.jsonl",
        "\n".join(
            json.dumps(x)
            for x in [u(False, "CR-PD-001", 100, 10, 0.5), u(False, "PR-RB-004", 50, 5, 0.25)]
        ),
    )
    write(art / "runs" / "live-1" / "timings.jsonl", "\n".join(json.dumps(x) for x in [
        {"model_id": "CR-PD-001", "stage": "discover", "seconds": 2.0}, {"model_id": "CR-PD-001", "stage": "document", "seconds": 3.0}]))  # fmt: skip
    write(
        art / "runs" / "replay-1" / "llm_usage.jsonl",
        json.dumps(u(True, "CR-PD-001", 100, 10, 0.5)),
    )
    write(
        art / "runs" / "replay-1" / "timings.jsonl",
        json.dumps({"model_id": "CR-PD-001", "stage": "discover", "seconds": 0.1}),
    )
    write(art / "CR-PD-001" / "documentation.json", {"grounding_score": 0.8})
    write(art / "CR-PD-002" / "parity_certificate.json", {"overall": "PASS", "attempt": 2, "levels": [
        {"level": "L1", "name": "coef", "passed": True, "value": 0.0, "tolerance": 1e-12}]})  # fmt: skip
    (art / "CR-PD-002" / "redevelop" / "attempt_1").mkdir(parents=True)
    (art / "CR-PD-002" / "redevelop" / "attempt_2").mkdir(parents=True)
    write(art / "CR-PD-002" / "validation_report.json", {"rating": "Fit with conditions", "findings": [{"severity": "high"}],
          "claims": [{"status": "supported"}, {"status": "unsupported"}], "results": {"tests": [{"rag": "green"}, {"rag": "red"}, {"rag": "green"}]}})  # fmt: skip
    write(
        art / "CR-PD-002" / "monitoring.json",
        {"trigger_month": 5, "points": [{}] * 6, "simulated": True},
    )
    audit.append("x", {})
    return tmp_path


def test_collect_from_artifacts_and_gold(world):
    m = bm.collect()
    assert m["runs"] == {"live": "live-1", "replay": "replay-1"}
    assert m["runtime"]["live"]["per_model_stage_s"] == {
        "CR-PD-001": {"discover": 2.0, "document": 3.0}
    }
    assert m["runtime"]["replay"]["total_s"] == 0.1
    assert m["llm_usage"]["total"] == {
        "calls": 2,
        "input_tokens": 150,
        "output_tokens": 15,
        "cache_hits": 0,
        "cost_usd": 0.75,
    }
    assert m["replay_cache_hits"] == 1.0
    acc = m["inventory_accuracy"]
    assert acc["deterministic"] == {
        "correct": 2,
        "total": 3,
        "accuracy": 0.6667,
    }  # upstream_models wrong
    assert acc["llm"] == {"correct": 4, "total": 4, "accuracy": 1.0}
    d = m["drift_detection"]
    assert (d["predicted"], d["true_positives"], d["gold_found"]) == (2, 1, 1)
    assert d["precision"] == 0.5 and d["recall"] == 0.5
    assert m["seeded_risks"]["per_risk"] == {
        "R1": True,
        "R2": True,
        "R3": False,
        "R4": True,
        "R5": True,
        "R6": True,
    }
    assert (
        m["grounding"]["documentation"]["CR-PD-001"] == 0.8
        and m["grounding"]["validation_narrative"] == 0.5
    )
    assert m["parity"]["self_heal_attempts"] == 1 and m["parity"]["levels"]["L1"]["passed"]
    assert (
        m["validation"]["rag_mix"] == {"green": 2, "red": 1}
        and m["monitoring"]["trigger_month"] == 5
    )
    assert m["governance"]["audit_chain_ok"] is True


def test_missing_sources_become_null_never_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "a")
    monkeypatch.setattr(config, "GOLD_DIR", tmp_path / "g")
    m = bm.collect()
    for k in (
        "llm_usage",
        "inventory_accuracy",
        "drift_detection",
        "seeded_risks",
        "parity",
        "validation",
        "monitoring",
    ):
        assert m[k] is None
    assert "n/a" in bm.results_table(m) and "None" not in bm.results_table(m)


def test_main_writes_metrics_and_refreshes_readme_table(world):
    (world / "README.md").write_text(
        f"intro\n{bm.README_MARKERS[0]}\nOLD\n{bm.README_MARKERS[1]}\noutro\n"
    )
    out = bm.main()
    assert json.loads(out.read_text())["parity"]["overall"] == "PASS"
    text = (world / "README.md").read_text()
    assert text.startswith("intro\n") and text.endswith("outro\n") and "OLD" not in text
    assert "| Parity certificate | PASS |" in text and "| Self-heal attempts | 1 |" in text


def test_real_gold_files_parse_and_score_empty_artifacts_as_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    m = bm.collect()  # real eval/gold, no artifacts: every gold item is counted, none is credited
    assert (
        m["inventory_accuracy"]["deterministic"]["total"] > 0
        and m["inventory_accuracy"]["llm"]["correct"] == 0
    )
    assert m["drift_detection"]["gold"] >= 10 and m["drift_detection"]["recall"] == 0.0
    assert m["seeded_risks"]["total"] >= 10 and m["seeded_risks"]["detected"] == 0
