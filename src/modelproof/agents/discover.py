"""Discover agent: facts + LLM semantics -> InventoryRecord. The LLM proposes; code disposes.

Deterministic (never LLM): risk tier, next due date, language, files, datasets, documentation
status, up/downstream models, and the verification of every doc vs code drift candidate."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from modelproof import audit, config, inventory, llm
from modelproof.schemas import Drift, Evidence, Facts, Feature, InventoryRecord

MAX_EXCERPT = 700  # chars of each evidence excerpt sent to the LLM
MAX_EVIDENCE = 150  # evidence items sent to the LLM
DOC_SUFFIXES = {
    ".md",
    ".rst",
    ".docx",
    ".pdf",
}  # formal documents; loose .txt notes are not documentation


class _Candidate(BaseModel):
    field: str
    doc_value: str
    code_value: str
    doc_evidence_id: str
    code_evidence_id: str


class _Semantic(BaseModel):
    """What the LLM may fill. Tiers, dates, files and statuses are computed by code."""

    name: str
    purpose: str = ""
    business_use: str = ""
    portfolio: str = ""
    model_type: Literal["PD", "LGD", "fraud", "pricing", "other"]
    methodology: str = ""
    target_definition: str = ""
    outputs: list[str] = []
    features: list[Feature] = []
    materiality: Literal["H", "M", "L"]
    materiality_rationale: str = ""
    complexity: Literal["H", "M", "L"]
    complexity_rationale: str = ""
    ai_ml_flag: bool = False
    regulatory_use: str = ""
    limitations: list[str] = []
    monitoring_kpis: list[str] = []
    owner_role: str = ""
    developer_role: str = ""
    validator_role: str = ""
    drift_candidates: list[_Candidate] = []


def _norm(s: str) -> str:
    return s.lower().replace("-", "_")


def _refs(dependencies: list[str], exclude: str | None = None) -> list[str]:
    """Model ids mentioned in dependency strings (case and - / _ insensitive)."""
    return [
        m for m in config.MODELS if m != exclude and any(_norm(m) in _norm(d) for d in dependencies)
    ]


def verified_drifts(candidates: list[_Candidate], evidence: list[Evidence]) -> list[Drift]:
    """Keep a candidate only if both evidence lines exist with the right kind, each line contains
    its quoted value, and the two values differ."""
    ev = {e.id: e for e in evidence}
    out: dict[tuple, Drift] = {}
    for c in candidates:
        d, k = ev.get(c.doc_evidence_id), ev.get(c.code_evidence_id)
        dv, cv = c.doc_value.strip(), c.code_value.strip()
        ok = d and k and d.kind == "doc" and k.kind == "code" and dv and cv and dv != cv
        if ok and dv in d.excerpt and cv in k.excerpt:
            fixed = {**c.model_dump(), "doc_value": dv, "code_value": cv}
            out.setdefault((c.field, dv, cv), Drift(**fixed, verified=True))
    return list(out.values())


def _prompt(facts: Facts, reviewer_comment: str) -> str:
    slim = facts.model_dump(exclude={"evidence"})
    parts = [
        "Extracted facts (JSON):",
        llm.untrusted(f"facts/{facts.model_id}.json", json.dumps(slim, default=str)),
        "Evidence excerpts (cite by id):",
    ]
    for e in facts.evidence[:MAX_EVIDENCE]:
        text = e.excerpt if len(e.excerpt) <= MAX_EXCERPT else e.excerpt[:MAX_EXCERPT] + " ..."
        parts.append(f"[{e.id}] {e.path}:{e.line_start}-{e.line_end} ({e.kind})")
        parts.append(llm.untrusted(e.path, text))
    if reviewer_comment:
        parts.append(
            f"A human reviewer rejected the previous inventory entry. Address this: {reviewer_comment}"
        )
    return "\n".join(parts)


def run(model_id: str, reviewer_comment: str = "") -> InventoryRecord:
    from modelproof import extract, security, tiering  # WP2 / WP3, imported lazily

    facts = extract.facts_for(model_id)
    flags = security.scan(model_id)
    sem = llm.structured(
        llm.load_prompt("discover"), _prompt(facts, reviewer_comment), _Semantic, "discover"
    )

    drifts = verified_drifts(sem.drift_candidates, facts.evidence)
    ev_ids = {e.id for e in facts.evidence}
    features = [
        f.model_copy(update={"evidence_id": f.evidence_id if f.evidence_id in ev_ids else None})
        for f in sem.features
    ]

    old = inventory.get(model_id)
    tier = tiering.assign(sem.materiality, sem.complexity)
    last_validated = old.last_validated if old else None
    has_doc = any(
        f.get("kind") == "doc" and Path(f["path"]).suffix.lower() in DOC_SUFFIXES
        for f in facts.files
    )
    downstream = []
    for other in config.MODELS:
        if other == model_id:
            continue
        try:
            deps = extract.facts_for(other).dependencies
        except Exception:  # an undiscoverable sibling is simply not a known dependant
            deps = []
        if model_id in _refs(deps):
            downstream.append(other)

    rec = InventoryRecord(
        **sem.model_dump(exclude={"features", "drift_candidates"}),
        model_id=model_id,
        features=features,
        platform_language=facts.language,
        source_files=facts.files,
        input_data=facts.datasets_read,
        upstream_models=_refs(facts.dependencies, exclude=model_id),
        downstream_models=downstream,
        risk_tier=tier,
        next_validation_due=tiering.next_due(tier, last_validated),
        last_validated=last_validated,
        documentation_status="missing" if not has_doc else "outdated" if drifts else "current",
        doc_code_drifts=drifts,
        security_flags=flags,
        status="discovered",
        approvals=old.approvals if old else [],
    )
    inventory.upsert(rec)
    audit.append(
        "discover.completed",
        {
            "risk_tier": tier,
            "documentation_status": rec.documentation_status,
            "drifts_proposed": len(sem.drift_candidates),
            "drifts_verified": len(drifts),
            "security_flags": len(flags),
            "upstream": rec.upstream_models,
            "downstream": downstream,
            "reviewer_comment": reviewer_comment,
        },
        model_id=model_id,
        actor="agent:discover",
    )
    return rec
