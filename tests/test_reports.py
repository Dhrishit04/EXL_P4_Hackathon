"""Report integration checks with explicitly synthetic artifact records."""

import json

import pytest

from modelproof import config
from modelproof.report import charts, render


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_artifact_reports_escape_sources_and_show_review(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    folder = tmp_path / "CR-PD-002"
    _save(folder / "documentation.json", {
        "model_id": "CR-PD-002", "grounding_score": 1.0, "generated_at": "2026-11-13T12:00:00Z",
        "claims": [{"section": "Purpose", "text": "<script>bad()</script>", "status": "supported",
                    "reason": "", "evidence_ids": ["E1"]}], "drifts": []})
    _save(folder / "facts.json", {"evidence": [{"id": "E1", "path": "model.R", "line_start": 1,
          "line_end": 2, "excerpt": "<unsafe>", "sha256": "abc"}]})
    doc = render.documentation("CR-PD-002").read_text()
    assert "&lt;script&gt;" in doc
    assert "<script>" not in doc
    assert "model.R:1" in doc
    assert "&lt;unsafe&gt;" in doc
    certificate = {"overall": "PASS", "run_id": "synthetic", "attempt": 1, "created_at": "2026-11-13",
                   "levels": [], "hashes": {}, "versions": {}, "mismatch_summary": {}}
    _save(folder / "parity_certificate.json", certificate)
    _save(folder / "redevelop" / "attempt_1" / "certificate.json", certificate)
    assert "Attempt 1" in render.parity("CR-PD-002").read_text()
    _save(folder / "validation_report.json", {"rating": "Fit with conditions", "created_at": "2026-11-13",
          "narrative": {"Summary": "Synthetic fixture"}, "results": {"tests": [
              {"test": "parity", "area": "implementation", "value": None, "threshold": "PASS",
               "rag": "amber", "ss123_principle": "P3"}], "charts": {}, "tables": {}}, "findings": []})
    audit = tmp_path / "audit" / "audit_log.jsonl"
    audit.parent.mkdir()
    audit.write_text(json.dumps({"model_id": "CR-PD-002", "actor": "tester", "ts": "2026-11-13",
                                "payload": {"gate": "validation", "decision": "approve", "auto": True}}))
    html = render.validation("CR-PD-002").read_text()
    assert "auto (demo flag)" in html
    assert "Unavailable" in html
    assert "data:image/png;base64," in html
    _save(tmp_path / "inventory" / "inventory.json", [{"model_id": "CR-PD-002", "name": "Fixture",
          "risk_tier": 1, "status": "validated", "documentation_status": "current",
          "doc_code_drifts": [], "security_flags": []}])
    assert "Fixture" in render.inventory().read_text()


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        render.documentation("../outside")


def test_chart_figures_and_png():
    figures = [charts.roc([0, 1], [0, 1]), charts.ks([0, 1], [0, 1], [0, 1]),
               charts.calibration([0.1, 0.7], [0.2, 0.8]), charts.score_distribution([1, 2], [2, 3]),
               charts.psi_by_month([1, 2], [0, 0.3], trigger_month=2), charts.fairness(["A", "B"], [0.4, 0.5])]
    for fig in figures:
        assert charts.to_base64(fig).startswith("iVBOR")
