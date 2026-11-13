from pathlib import Path

import yaml

from modelproof import config

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"
MODEL_IDS = {"CR-PD-001", "CR-PD-002", "FR-TX-003", "PR-RB-004"}


def lines(model_id: str, suffixes: set[str]) -> list[str]:
    return [ln for f in config.model_dir(model_id).iterdir() if f.suffix in suffixes for ln in f.read_text().splitlines()]


def test_no_src_or_prompt_reads_gold():
    for d in ("src", "prompts"):
        for f in (ROOT / d).rglob("*"):
            if f.is_file() and f.suffix in {".py", ".md", ".j2", ".yaml"} and f.name != "config.py":
                assert "eval/gold" not in f.read_text(), f


def test_seeded_drift_values_appear_verbatim_in_the_doc_line_and_code_line():
    drifts = yaml.safe_load((GOLD / "seeded_drifts.yaml").read_text())
    assert len(drifts) >= 14 and sum(d["model_id"] == "CR-PD-002" for d in drifts) >= 6
    for d in drifts:
        assert any(d["doc_value"] in ln for ln in lines(d["model_id"], {".md", ".txt"})), d["id"]
        assert any(d["code_value"] in ln for ln in lines(d["model_id"], {".sas", ".R", ".py"})), d["id"]


def test_seeded_risks_use_the_b11_kinds_and_keywords_exist_in_the_estate():
    risks = yaml.safe_load((GOLD / "seeded_risks.yaml").read_text())
    assert {r["kind"] for r in risks} == {"proxy", "injection", "dead_variable", "dependency"}
    for r in risks:
        assert set(r) == {"id", "model_id", "kind", "keyword"}
        if r["kind"] != "dependency":
            assert any(r["keyword"].lower() in ln.lower() for ln in lines(r["model_id"], {".sas", ".R", ".py", ".md", ".txt"})), r["id"]


def test_inventory_gold_is_b11_shaped_and_covers_all_models():
    inv = yaml.safe_load((GOLD / "inventory_gold.yaml").read_text())
    assert set(inv) == MODEL_IDS and all(set(v) == {"deterministic", "llm"} for v in inv.values())
    assert inv["PR-RB-004"]["deterministic"]["upstream_models"] == ["CR-PD-001"]
    assert inv["CR-PD-001"]["deterministic"]["downstream_models"] == ["PR-RB-004"]
