"""Agents and prompts must never read the held-out ground truth (eval/gold)."""

from modelproof import config

NEEDLES = ("eval/gold", "eval\\gold", "GOLD_DIR", "inventory_gold", "seeded_drifts", "seeded_risks")


def test_src_and_prompts_never_reference_eval_gold():
    offenders = []
    for folder in (config.ROOT / "src", config.ROOT / "prompts"):
        for f in folder.rglob("*"):
            if f.is_file() and f.suffix in {".py", ".md", ".j2", ".yaml", ".txt"}:
                if f.name == "config.py" and f.parent.name == "modelproof":
                    continue  # defines GOLD_DIR for scripts/benchmark.py only
                text = f.read_text(encoding="utf-8", errors="ignore")
                offenders += [f"{f.relative_to(config.ROOT)}: {n}" for n in NEEDLES if n in text]
    assert not offenders, offenders
