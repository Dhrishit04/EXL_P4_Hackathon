"""Test-only stand-in for Varun's modelproof.config (used only if the real one is not on the path)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW, DATA_PROCESSED = ROOT / "data/raw", ROOT / "data/processed"
LEGACY, GOLD_DIR, REBUILT, CACHE = ROOT / "legacy_estate", ROOT / "eval/gold", ROOT / "rebuilt", ROOT / ".cache/llm"
ARTIFACTS = Path(__import__("os").environ.get("MODELPROOF_ARTIFACTS", ROOT / "artifacts"))
MODELS = {
    "CR-PD-001": "CR-PD-001_sas_application_scorecard",
    "CR-PD-002": "CR-PD-002_r_card_default_pd",
    "FR-TX-003": "FR-TX-003_py_card_fraud",
    "PR-RB-004": "PR-RB-004_sas_risk_based_pricing",
}
REBUILD_TARGET = "CR-PD-002"
_POLICY = """
seed: 42
parity: {coef_load_abs: 1.0e-12, coef_refit_abs: 1.0e-6, pd_abs: 1.0e-9}
max_redevelop_attempts: 4
"""


def load_policy() -> dict:
    return yaml.safe_load(_POLICY)


def artifact_dir(model_id: str) -> Path:
    d = ARTIFACTS / model_id
    d.mkdir(parents=True, exist_ok=True)
    return d
