from __future__ import annotations

import json
from pathlib import Path

from modelproof import audit, config, schemas

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "artifacts_sample"
MODEL_IDS = ("CR-PD-001", "CR-PD-002", "FR-TX-003", "PR-RB-004")


def test_all_schema_fixtures_validate() -> None:
    inventory = json.loads((FIXTURES / "inventory" / "inventory.json").read_text(encoding="utf-8"))
    assert len([schemas.InventoryRecord.model_validate(record) for record in inventory]) == len(MODEL_IDS)

    for model_id in MODEL_IDS:
        model_dir = FIXTURES / model_id
        schemas.Facts.model_validate_json((model_dir / "facts.json").read_text(encoding="utf-8"))
        schemas.Documentation.model_validate_json(
            (model_dir / "documentation.json").read_text(encoding="utf-8")
        )
        schemas.ParityCertificate.model_validate_json(
            (model_dir / "parity_certificate.json").read_text(encoding="utf-8")
        )
        schemas.ValidationResults.model_validate_json(
            (model_dir / "validation_results.json").read_text(encoding="utf-8")
        )
        schemas.ValidationReport.model_validate_json(
            (model_dir / "validation_report.json").read_text(encoding="utf-8")
        )
        schemas.MonitoringResult.model_validate_json(
            (model_dir / "monitoring.json").read_text(encoding="utf-8")
        )
        for certificate_path in (model_dir / "redevelop").glob("attempt_*/certificate.json"):
            schemas.ParityCertificate.model_validate_json(
                certificate_path.read_text(encoding="utf-8")
            )


def test_fixture_audit_chain_verifies(monkeypatch) -> None:
    monkeypatch.setattr(config, "ARTIFACTS", FIXTURES)
    assert audit.verify_chain()
