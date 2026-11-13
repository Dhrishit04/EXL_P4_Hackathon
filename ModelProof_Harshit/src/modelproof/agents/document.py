"""Document agent: the LLM writes evidence-linked claims, verify.verify grades them deterministically.
The LLM only sees facts, code/doc excerpts (wrapped as untrusted) and validation metrics, never rows."""

import json
from datetime import UTC, datetime

from pydantic import BaseModel

from modelproof import audit, config, inventory, llm
from modelproof.agents import verify
from modelproof.schemas import Claim, Documentation, Facts, ValidationResults

SECTIONS = [
    "1 Purpose and use",
    "2 Data and target definition",
    "3 Methodology",
    "4 Variables and transformations",
    "5 Assumptions",
    "6 Limitations and known issues",
    "7 Performance at development",
    "8 Implementation and dependencies",
    "9 Monitoring plan",
    "10 Open findings and change log",
]
MAX_EXCERPT = 600  # chars sent per evidence item
MAX_EVIDENCE_CHARS = 60_000  # total evidence budget in the prompt


class _Claim(BaseModel):
    section: str
    text: str
    evidence_ids: list[str] = []


class _Claims(BaseModel):
    claims: list[_Claim]


def _metrics(model_id: str) -> dict | None:
    """Validation numbers as {test: {value, rag, threshold, details}}; None before validation."""
    p = config.artifact_dir(model_id) / "validation_results.json"
    if not p.exists():
        return None
    res = ValidationResults.model_validate_json(p.read_text())
    return {
        t.test: {"value": t.value, "rag": t.rag, "threshold": t.threshold, "details": t.details}
        for t in res.tests
    }


def _evidence_block(facts: Facts) -> str:
    parts, used = [], 0
    for e in facts.evidence:
        item = f"[{e.id}] {e.kind} {e.path}:{e.line_start}-{e.line_end}\n" + llm.untrusted(
            e.path, e.excerpt[:MAX_EXCERPT]
        )
        if used + len(item) > MAX_EVIDENCE_CHARS:
            parts.append(f"(... {len(facts.evidence) - len(parts)} more evidence items omitted)")
            break
        parts.append(item)
        used += len(item)
    return "\n\n".join(parts)


def _user_prompt(facts: Facts, metrics: dict | None, comment: str) -> str:
    rec = inventory.get(facts.model_id)
    brief = facts.model_dump(mode="json", exclude={"evidence", "files"})
    files = [{k: f.get(k) for k in ("path", "kind", "n_lines")} for f in facts.files]
    out = [
        f"Model id: {facts.model_id} ({facts.language})",
        "Sections to write (use these exact names):\n" + "\n".join(SECTIONS),
        "FACTS (deterministic extraction):\n"
        + llm.untrusted(
            f"facts/{facts.model_id}.json", json.dumps({**brief, "files": files}, indent=1)
        ),
        "EVIDENCE (cite only these ids):\n" + _evidence_block(facts),
    ]
    if metrics:
        out.append(
            "VALIDATION METRICS (section 7 numbers may come ONLY from here; cite the metric id = "
            "the top-level key):\n" + json.dumps(metrics, indent=1, default=str)
        )
    else:
        out.append(
            "VALIDATION METRICS: none yet. Section 7 must be one claim saying performance at "
            "development is pending validation, with no numbers."
        )
    if rec and (rec.doc_code_drifts or rec.security_flags):
        out.append(
            "KNOWN FINDINGS for section 10 (cite their evidence ids):\n"
            + json.dumps(
                {
                    "doc_code_drifts": [d.model_dump(mode="json") for d in rec.doc_code_drifts],
                    "security_flags": [f.model_dump(mode="json") for f in rec.security_flags],
                },
                indent=1,
            )
        )
    if comment:
        out.append(f"REVIEWER FEEDBACK on the rejected previous draft (address it):\n{comment}")
    return "\n\n".join(out)


def run(model_id: str, reviewer_comment: str = "") -> Documentation:
    from modelproof.extract import facts_for  # WP2, imported lazily

    facts = facts_for(model_id)
    metrics = _metrics(model_id)
    drafted = llm.structured(
        llm.load_prompt("document"),
        _user_prompt(facts, metrics, reviewer_comment),
        _Claims,
        "document",
    )
    claims, grounding = verify.verify(
        [
            Claim(section=c.section, text=c.text, evidence_ids=c.evidence_ids)
            for c in drafted.claims
        ],
        facts,
        metrics,
    )
    rec = inventory.get(model_id)
    doc = Documentation(
        model_id=model_id,
        claims=claims,
        grounding_score=grounding,
        drifts=[d for d in rec.doc_code_drifts if d.verified] if rec else [],
        generated_at=datetime.now(UTC),
    )
    (config.artifact_dir(model_id) / "documentation.json").write_text(doc.model_dump_json(indent=2))
    audit.append(
        "document.completed",
        {
            "grounding": round(grounding, 4),
            "n_claims": len(claims),
            "n_unsupported": sum(c.status != "supported" for c in claims),
        },
        model_id=model_id,
        actor="agent:document",
    )
    return doc
