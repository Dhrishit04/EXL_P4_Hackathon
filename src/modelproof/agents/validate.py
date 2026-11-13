"""Validate agent: run the deterministic suite, let the LLM narrate it, verify the narrative.

The LLM sees only the results JSON (aggregates, never rows). RAG status and the rating come from
`validation.rating`, never from the LLM."""

import json
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from modelproof import audit, config, inventory, llm
from modelproof.schemas import Claim, Finding, ValidationReport, ValidationResults

MAX_TABLE_ROWS = 5
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_NUM = re.compile(r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class _Section(BaseModel):
    area: str
    text: str


class _Finding(BaseModel):
    area: str
    severity: Literal["high", "medium", "low"]
    ss123_principle: Literal["P1", "P2", "P3", "P4", "P5"]
    description: str
    evidence_ids: list[str] = []
    recommendation: str = ""


class _Narrative(BaseModel):
    sections: list[_Section]
    findings: list[_Finding] = []


def _scalars(d: dict, max_len: int = 8) -> dict:
    """Keep scalar details and short containers; drop anything large."""
    return {
        k: v
        for k, v in d.items()
        if v is None
        or isinstance(v, str | int | float | bool)
        or (isinstance(v, list | dict) and len(v) <= max_len)
    }


def _results_json(results: ValidationResults) -> str:
    tests = [
        {
            "test": t.test,
            "area": t.area,
            "value": t.value,
            "threshold": t.threshold,
            "rag": t.rag,
            "details": _scalars(t.details),
        }
        for t in results.tests
    ]
    tables = {k: {"n_rows": len(v), "head": v[:MAX_TABLE_ROWS]} for k, v in results.tables.items()}
    return json.dumps({"model_id": results.model_id, "tests": tests, "tables": tables}, default=str)


def _metrics(results: ValidationResults) -> dict:
    """Traceable numbers per test: its value, numeric details and the numbers in its threshold."""
    out = {}
    for t in results.tests:
        m = {
            k: v
            for k, v in t.details.items()
            if isinstance(v, int | float) and not isinstance(v, bool)
        }
        m["value"] = t.value
        m |= {f"threshold_{i}": float(x) for i, x in enumerate(_NUM.findall(t.threshold))}
        out[t.test] = m
    return out


def _features(model_id: str, dev) -> list[str]:
    rec = inventory.get(model_id)
    named = [f.name for f in rec.features if f.name in dev.columns] if rec else []
    return named or [c for c in dev.columns if c not in ("ID", "DEFAULT")]


def _claims(
    narrative: _Narrative, findings: list[Finding], results: ValidationResults
) -> list[Claim]:
    by_area: dict[str, list[str]] = {}
    for t in results.tests:
        by_area.setdefault(t.area, []).append(t.test)
    claims = [
        Claim(section=s.area, text=sent, evidence_ids=by_area.get(s.area, []))
        for s in narrative.sections
        for sent in _SENTENCE.split(s.text.strip())
        if sent
    ]
    claims += [
        Claim(
            section="findings",
            text=f.description,
            evidence_ids=f.evidence_ids or by_area.get(f.area, []),
        )
        for f in findings
    ]
    return claims


def run(model_id: str = "CR-PD-002", reviewer_comment: str = "") -> ValidationReport:
    from modelproof import data, extract, parity, validation  # WP2 / WP3, imported lazily
    from modelproof.agents import verify

    dev, holdout = data.load_cr_pd_002("dev"), data.load_cr_pd_002("holdout")
    fn = parity.score_fn(config.REBUILT / "cr_pd_002.py")
    results = validation.run_suite(model_id, dev, holdout, fn, _features(model_id, dev))

    user = "Validation results (JSON):\n" + llm.untrusted(
        f"validation_results/{model_id}.json", _results_json(results)
    )
    if reviewer_comment:
        user += f"\nA human reviewer rejected the previous report. Address this: {reviewer_comment}"
    out = llm.structured(llm.load_prompt("validate"), user, _Narrative, "validate")

    areas = {t.area for t in results.tests}
    tests = {t.test for t in results.tests}
    narrative = {s.area: s.text for s in out.sections if s.area in areas}
    findings = [
        Finding(
            id=f"VF-{i}",
            model_id=model_id,
            area=f.area,
            severity=f.severity,
            ss123_principle=f.ss123_principle,
            description=f.description,
            evidence_ids=[e for e in f.evidence_ids if e in tests],
            recommendation=f.recommendation,
        )
        for i, f in enumerate(out.findings, 1)
    ]
    claims, grounding = verify.verify(
        _claims(
            _Narrative(sections=[s for s in out.sections if s.area in areas]), findings, results
        ),
        extract.facts_for(model_id),
        _metrics(results),
    )
    report = ValidationReport(
        model_id=model_id,
        results=results,
        narrative=narrative,
        findings=findings,
        rating=validation.rating(results.tests),
        claims=claims,
        created_at=datetime.now(UTC),
    )
    (config.artifact_dir(model_id) / "validation_report.json").write_text(
        report.model_dump_json(indent=2)
    )
    try:
        from modelproof.report import render

        render.validation(model_id)
    except ImportError as e:  # WP3 renderer not available: the JSON report is still complete
        audit.append(
            "validate.render_skipped", {"reason": str(e)}, model_id=model_id, actor="agent:validate"
        )
    audit.append(
        "validate.completed",
        {
            "rating": report.rating,
            "n_tests": len(results.tests),
            "n_findings": len(findings),
            "grounding": grounding,
            "reviewer_comment": reviewer_comment,
        },
        model_id=model_id,
        actor="agent:validate",
    )
    return report
