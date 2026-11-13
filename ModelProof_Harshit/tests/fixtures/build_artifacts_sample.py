from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import sys
import zlib
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modelproof import schemas  # noqa: E402

ROOT = Path(__file__).resolve().parent / "artifacts_sample"
MODEL_IDS = (
    "CR-PD-001",
    "CR-PD-002",
    "FR-TX-003",
    "PR-RB-004",
)


def write_json(relative_path: str, data: object) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_schema_json(relative_path: str, schema: type, data: dict) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    model = schema.model_validate(data)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_schema_list(relative_path: str, schema: type, records: list[dict]) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        schema.model_validate(record).model_dump_json(indent=2)
        for record in records
    ]
    path.write_text("[\n" + ",\n".join(serialized) + "\n]\n", encoding="utf-8")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_fixture_png(path: Path) -> None:
    width, height = 1, 1
    raw = b"\x00\xF2\x8C\x28"
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def inventory_record(model_id: str, language: str, model_type: str, status: str) -> dict:
    return {
        "model_id": model_id,
        "name": f"FIXTURE example model {model_id}",
        "purpose": "FIXTURE synthetic example only",
        "business_use": "FIXTURE not a real business use",
        "portfolio": "FIXTURE portfolio",
        "model_type": model_type,
        "methodology": "FIXTURE illustrative methodology",
        "platform_language": language,
        "source_files": [],
        "input_data": ["FIXTURE synthetic input"],
        "features": [{"name": "FIXTURE illustrative feature", "transformation": "FIXTURE identity"}],
        "target_definition": "FIXTURE illustrative target",
        "outputs": ["FIXTURE illustrative output"],
        "upstream_models": [],
        "downstream_models": [],
        "owner_role": "FIXTURE owner",
        "developer_role": "FIXTURE developer",
        "validator_role": "FIXTURE validator",
        "materiality": "M",
        "materiality_rationale": "FIXTURE illustrative rationale",
        "complexity": "M",
        "complexity_rationale": "FIXTURE illustrative rationale",
        "risk_tier": 2,
        "ai_ml_flag": False,
        "regulatory_use": "FIXTURE not used for a regulatory decision",
        "documentation_status": "outdated",
        "doc_code_drifts": [{
            "field": "FIXTURE illustrative field",
            "doc_value": "FIXTURE documented value",
            "code_value": "FIXTURE code value",
            "doc_evidence_id": "FIXTURE-DOC-1",
            "code_evidence_id": "FIXTURE-CODE-1",
            "verified": True,
        }],
        "security_flags": [{
            "id": "FIXTURE-FINDING-1",
            "model_id": model_id,
            "area": "FIXTURE security",
            "severity": "medium",
            "ss123_principle": "P4",
            "description": "FIXTURE seeded example security flag",
            "evidence_ids": [],
            "recommendation": "FIXTURE review this synthetic example",
            "status": "open",
        }] if model_id == "PR-RB-004" else [],
        "last_validated": "2026-01-01",
        "next_validation_due": "2027-01-01",
        "monitoring_kpis": ["FIXTURE PSI"],
        "limitations": ["FIXTURE synthetic example; not a model result"],
        "status": status,
        "approvals": [],
    }


def certificate(model_id: str, passed: bool) -> dict:
    return {
        "model_id": model_id,
        "overall": "PASS" if passed else "FAIL",
        "levels": [
            {
                "level": f"L{number}",
                "name": f"FIXTURE parity level {number}",
                "passed": passed,
                "metric": "FIXTURE max absolute difference",
                "value": 0.000000001 if passed else 0.1,
                "tolerance": 0.000000001,
                "details": {"note": "FIXTURE synthetic certificate"},
            }
            for number in range(1, 6)
        ],
        "hashes": {"source": "FIXTURE-source-hash", "rebuilt": "FIXTURE-rebuilt-hash"},
        "versions": {"python": "FIXTURE 3.11", "model": "FIXTURE 1.0"},
        "mismatch_summary": {},
        "attempt": 2 if passed else 1,
        "run_id": "FIXTURE-run",
        "created_at": "2026-01-01T00:00:00Z",
    }


def build() -> None:
    languages = ("SAS", "R", "Python", "SAS")
    types = ("PD", "PD", "fraud", "pricing")
    statuses = ("documented", "validated", "discovered", "documented")
    records = [
        inventory_record(model_id, language, model_type, status)
        for model_id, language, model_type, status in zip(MODEL_IDS, languages, types, statuses)
    ]
    write_schema_list("inventory/inventory.json", schemas.InventoryRecord, records)
    (ROOT / "inventory" / "inventory.csv").write_text(
        "FIXTURE model_id,name\n" + "".join(f'{model_id},"FIXTURE example model"\n' for model_id in MODEL_IDS),
        encoding="utf-8",
    )
    (ROOT / "inventory" / "inventory.html").write_text(
        "<!doctype html><title>FIXTURE inventory</title><p>FIXTURE synthetic example</p>",
        encoding="utf-8",
    )
    (ROOT / "runs" / "FIXTURE-run").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "FIXTURE-run" / "llm_usage.jsonl").write_text(
        json.dumps({
            "ts": "FIXTURE timestamp",
            "task": "FIXTURE task",
            "provider": "FIXTURE provider",
            "model": "FIXTURE model",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
            "cache_hit": True,
        }) + "\n",
        encoding="utf-8",
    )
    with sqlite3.connect(ROOT / "checkpoints.sqlite"):
        pass
    (ROOT / "audit").mkdir(parents=True, exist_ok=True)
    audit_entries = []
    previous_hash = "0" * 64
    for model_id in MODEL_IDS:
        entry = {
            "ts": "2026-01-01T00:00:00Z",
            "actor": "FIXTURE reviewer",
            "event": "FIXTURE approval",
            "model_id": model_id,
            "payload": {"decision": "FIXTURE approved for illustration only"},
            "prev_hash": previous_hash,
        }
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        entry["hash"] = hashlib.sha256((previous_hash + canonical).encode()).hexdigest()
        previous_hash = entry["hash"]
        audit_entries.append(entry)
    (ROOT / "audit" / "audit_log.jsonl").write_text(
        "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in audit_entries),
        encoding="utf-8",
    )
    write_json("metrics.json", {
        "runtime_per_model_seconds": 12.34,
        "grounding_score": 0.91,
        "note": "FIXTURE values are intentionally fabricated and must not be presented as results",
    })

    for model_id, language in zip(MODEL_IDS, languages):
        prefix = model_id + "/"
        write_schema_json(prefix + "facts.json", schemas.Facts, {
            "model_id": model_id,
            "language": language,
            "files": [{"path": "FIXTURE/example.txt", "sha256": "FIXTURE-hash", "n_lines": 3, "kind": "code"}],
            "datasets_read": ["FIXTURE synthetic dataset"],
            "datasets_written": [],
            "variables_created": ["FIXTURE_FEATURE"],
            "variables_used": ["FIXTURE_TARGET"],
            "dead_variables": [],
            "model_calls": [],
            "target": "FIXTURE_TARGET",
            "parameters": {},
            "dependencies": [],
            "evidence": [{
                "id": "FIXTURE-CODE-1",
                "kind": "code",
                "path": "FIXTURE/example.txt",
                "line_start": 1,
                "line_end": 2,
                "excerpt": "FIXTURE synthetic example source",
                "sha256": "FIXTURE-hash",
            }, {
                "id": "FIXTURE-DOC-1",
                "kind": "doc",
                "path": "FIXTURE/model_documentation.txt",
                "line_start": 4,
                "line_end": 4,
                "excerpt": "FIXTURE synthetic documented value",
                "sha256": "FIXTURE-doc-hash",
            }],
        })
        write_schema_json(prefix + "documentation.json", schemas.Documentation, {
            "model_id": model_id,
            "claims": [{
                "section": "FIXTURE Overview",
                "text": "FIXTURE illustrative documentation claim",
                "evidence_ids": ["FIXTURE-CODE-1"],
                "status": "supported",
                "reason": "FIXTURE supported only by synthetic evidence",
            }],
            "grounding_score": 0.91,
            "drifts": [{
                "field": "FIXTURE illustrative field",
                "doc_value": "FIXTURE documented value",
                "code_value": "FIXTURE code value",
                "doc_evidence_id": "FIXTURE-DOC-1",
                "code_evidence_id": "FIXTURE-CODE-1",
                "verified": True,
            }],
            "generated_at": "2026-01-01T00:00:00Z",
        })
        (ROOT / prefix / "documentation.html").write_text(
            "<!doctype html><title>FIXTURE documentation</title>"
            "<p>FIXTURE synthetic evidence-linked documentation.</p>",
            encoding="utf-8",
        )
        attempts = [
            {
                "attempt": 1,
                "overall": "FAIL",
                "passed_levels": ["L1", "L2"],
                "localiser_summary": "FIXTURE localiser summary: synthetic coefficient mismatch.",
            },
            {
                "attempt": 2,
                "overall": "PASS",
                "passed_levels": ["L1", "L2", "L3", "L4", "L5"],
                "localiser_summary": "FIXTURE localiser summary: synthetic retry passed.",
            },
        ]
        write_json(prefix + "redevelop/attempts.json", attempts)
        for attempt in attempts:
            attempt_dir = ROOT / prefix / "redevelop" / f"attempt_{attempt['attempt']}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            (attempt_dir / "cr_pd_002.py").write_text(
                "# FIXTURE synthetic rebuild placeholder\n", encoding="utf-8"
            )
            (attempt_dir / "test_cr_pd_002.py").write_text(
                "# FIXTURE synthetic test placeholder\n", encoding="utf-8"
            )
            (attempt_dir / "test_output.txt").write_text(
                f"FIXTURE {attempt['overall']} synthetic test output\n", encoding="utf-8"
            )
            write_schema_json(
                prefix + f"redevelop/attempt_{attempt['attempt']}/certificate.json",
                schemas.ParityCertificate,
                certificate(model_id, attempt["overall"] == "PASS"),
            )
        write_schema_json(
            prefix + "parity_certificate.json",
            schemas.ParityCertificate,
            certificate(model_id, True),
        )
        (ROOT / prefix / "parity_certificate.html").write_text(
            "<!doctype html><title>FIXTURE parity certificate</title>"
            "<p>FIXTURE synthetic parity result.</p>",
            encoding="utf-8",
        )
        calibration_records = [
            {"bin": "FIXTURE bin 1", "n": 10, "mean_predicted": 0.1, "observed_rate": 0.12},
            {"bin": "FIXTURE bin 2", "n": 10, "mean_predicted": 0.2, "observed_rate": 0.18},
        ]
        write_schema_json(prefix + "validation_results.json", schemas.ValidationResults, {
            "model_id": model_id,
            "tests": [{
                "test": "FIXTURE discrimination check",
                "area": "discrimination",
                "value": 0.73,
                "threshold": "FIXTURE illustrative threshold",
                "rag": "amber",
                "ss123_principle": "P4",
                "details": {"note": "FIXTURE fabricated metric"},
            }],
            "tables": {
                "calibration": calibration_records,
                "fairness": [{
                    "sensitive": "FIXTURE protected feature",
                    "group": "FIXTURE group",
                    "n": 10,
                    "approval_rate": 0.6,
                    "tpr": 0.5,
                    "fpr": 0.2,
                    "auc": 0.7,
                    "uncertain": True,
                }],
            },
            "charts": {
                "roc": {"fpr": [0.0, 0.5, 1.0], "tpr": [0.0, 0.7, 1.0]},
                "ks": {"score": [0.1, 0.5, 0.9], "good_cdf": [0.2, 0.6, 1.0], "bad_cdf": [0.1, 0.8, 1.0]},
                "score_distribution": {"edges": [0, 50, 100], "dev": [4, 6], "holdout": [5, 5]},
                "calibration": {"records": calibration_records},
            },
        })
        write_schema_json(prefix + "validation_report.json", schemas.ValidationReport, {
            "model_id": model_id,
            "results": {
                "model_id": model_id,
                "tests": [{
                    "test": "FIXTURE discrimination check",
                    "area": "discrimination",
                    "value": 0.73,
                    "threshold": "FIXTURE illustrative threshold",
                    "rag": "amber",
                    "ss123_principle": "P4",
                    "details": {},
                }],
                "tables": {
                    "calibration": calibration_records,
                    "fairness": [{
                        "sensitive": "FIXTURE protected feature",
                        "group": "FIXTURE group",
                        "n": 10,
                        "approval_rate": 0.6,
                        "tpr": 0.5,
                        "fpr": 0.2,
                        "auc": 0.7,
                        "uncertain": True,
                    }],
                },
                "charts": {},
            },
            "narrative": {"summary": "FIXTURE illustrative summary only"},
            "findings": [{
                "id": "FIXTURE-REPORT-FINDING",
                "model_id": model_id,
                "area": "FIXTURE validation",
                "severity": "medium",
                "ss123_principle": "P4",
                "description": "FIXTURE example finding, not a model conclusion",
                "evidence_ids": [],
                "recommendation": "FIXTURE no action; illustrative only",
                "status": "open",
            }],
            "rating": "Fit with conditions",
            "claims": [],
            "created_at": "2026-01-01T00:00:00Z",
        })
        (ROOT / prefix / "validation_report.html").write_text(
            "<!doctype html><title>FIXTURE validation report</title>"
            "<p>FIXTURE synthetic validation result.</p>",
            encoding="utf-8",
        )
        write_schema_json(prefix + "monitoring.json", schemas.MonitoringResult, {
            "model_id": model_id,
            "points": [
                {"month": 1, "score_psi": 0.08, "csi": {"FIXTURE_FEATURE": 0.07}, "gini": 0.71,
                 "observed_dr": 0.08, "expected_dr": 0.07, "jeffreys_failures": 0, "breaches": []},
                {"month": 2, "score_psi": 0.28, "csi": {"FIXTURE_FEATURE": 0.26}, "gini": 0.62,
                 "observed_dr": 0.11, "expected_dr": 0.07, "jeffreys_failures": 1,
                 "breaches": ["FIXTURE simulated PSI breach"]},
            ],
            "trigger_month": 2,
            "simulated": True,
        })
        write_fixture_png(ROOT / prefix / "monitoring.png")


if __name__ == "__main__":
    build()
