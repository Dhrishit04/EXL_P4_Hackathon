from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"


def line(path: str, n: int) -> str:
    return (ROOT / path).read_text().splitlines()[n - 1]


def test_no_src_or_prompt_reads_gold():
    for d in ("src", "prompts"):
        for f in (ROOT / d).rglob("*"):
            if f.is_file() and f.suffix in {".py", ".md", ".j2", ".yaml"}:
                assert "eval/gold" not in f.read_text(), f


def test_seeded_drifts_point_at_the_planted_lines():
    drifts = yaml.safe_load((GOLD / "seeded_drifts.yaml").read_text())
    assert len(drifts) >= 14
    for d in drifts:
        assert d["doc_anchor"] in line(d["doc_file"], d["doc_line"]), d["id"]
        assert d["code_anchor"] in line(d["code_file"], d["code_line"]), d["id"]
    assert sum(d["model_id"] == "CR-PD-002" for d in drifts) >= 6


def test_seeded_risks_point_at_the_planted_lines():
    risks = yaml.safe_load((GOLD / "seeded_risks.yaml").read_text())
    kinds = {r["kind"] for r in risks}
    assert {"proxy_variable", "prompt_injection", "dead_variable", "dependency", "stale_comment"} <= kinds
    for r in risks:
        assert r["anchor"] in line(r["file"], r["line"]), r["id"]


def test_inventory_gold_covers_all_models():
    inv = yaml.safe_load((GOLD / "inventory_gold.yaml").read_text())
    assert set(inv) == {"CR-PD-001", "CR-PD-002", "FR-TX-003", "PR-RB-004"}
    assert inv["PR-RB-004"]["upstream_models"] == ["CR-PD-001"] and inv["CR-PD-001"]["downstream_models"] == ["PR-RB-004"]
