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
            input_data=["raw.german"],
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
    write(gold / "inventory_gold.yaml", yaml.dump({"CR-PD-001": {
        "deterministic": {"platform_language": "sas", "downstream_models": ["PR-RB-004"], "upstream_models": ["X"], "input_data": ["raw.*"]},
        "llm": {"model_type": "PD", "risk_tier": 1, "target_definition_contains": ["bad"]}}}))  # fmt: skip
    write(gold / "seeded_drifts.yaml", yaml.dump([
        {"id": "D1", "model_id": "CR-PD-001", "field": "cutoff", "doc_value": "0.5", "code_value": "0.6"},
        {"id": "D2", "model_id": "CR-PD-001", "field": "other", "doc_value": "9", "code_value": "10"}]))  # fmt: skip
    write(gold / "seeded_risks.yaml", yaml.dump([
        {"id": "R1", "model_id": "CR-PD-001", "kind": "proxy", "keyword": "personal_status"},
        {"id": "R2", "model_id": "PR-RB-004", "kind": "dependency", "keyword": "CR-PD-001"},
        {"id": "R3", "model_id": "PR-RB-004", "kind": "injection", "keyword": "ignore previous"},
        {"id": "R4", "model_id": "CR-PD-001", "kind": "dead_variable", "keyword": "debt_ratio"}]))  # fmt: skip
    write(art / "CR-PD-001" / "facts.json", {"dead_variables": ["debt_ratio"]})

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
        "correct": 3,
        "total": 4,
        "accuracy": 0.75,
    }  # upstream_models wrong
    assert acc["llm"] == {"correct": 3, "total": 3, "accuracy": 1.0}
    d = m["drift_detection"]
    assert (d["predicted"], d["true_positives"], d["gold_found"]) == (2, 1, 1)
    assert d["precision"] == 0.5 and d["recall"] == 0.5
    assert m["seeded_risks"]["per_risk"] == {"R1": True, "R2": True, "R3": False, "R4": True}
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
    assert m["seeded_risks"]["total"] >= 5 and m["seeded_risks"]["detected"] == 0
