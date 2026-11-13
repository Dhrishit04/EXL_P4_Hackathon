"""Paths, model registry and policy loader. Read `config.ARTIFACTS` / `config.CACHE` at call time
(not `from ... import ARTIFACTS`) so tests can monkeypatch them."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
LEGACY = ROOT / "legacy_estate"
GOLD_DIR = ROOT / "eval" / "gold"
REBUILT = ROOT / "rebuilt"
CACHE = ROOT / ".cache" / "llm"
_art = Path(os.environ.get("MODELPROOF_ARTIFACTS") or "artifacts")
ARTIFACTS = _art if _art.is_absolute() else ROOT / _art

# model_id -> folder (repo relative, as in CONTRACT B1)
MODELS: dict[str, str] = {
    "CR-PD-001": "legacy_estate/CR-PD-001_sas_application_scorecard",
    "CR-PD-002": "legacy_estate/CR-PD-002_r_card_default_pd",
    "FR-TX-003": "legacy_estate/FR-TX-003_py_card_fraud",
    "PR-RB-004": "legacy_estate/PR-RB-004_sas_risk_based_pricing",
}
REBUILD_TARGET = "CR-PD-002"


def load_policy() -> dict:
    return yaml.safe_load((ROOT / "config" / "policy.yaml").read_text())


def model_dir(model_id: str) -> Path:
    return ROOT / MODELS[model_id]


def artifact_dir(model_id: str) -> Path:
    d = ARTIFACTS / model_id
    d.mkdir(parents=True, exist_ok=True)
    return d
