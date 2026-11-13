"""Security scanner: prompt injection in sources and documents, protected-attribute proxies used by code."""
import re
from pathlib import Path

from modelproof import extract
from modelproof.schemas import Finding

PATTERNS = re.compile(
    r"ignore\s+(?:all|previous)\s+instructions|you\s+are\s+an\s+ai\b|system\s+prompt|classify\s+this\s+model\s+as"
    r"|mark\s+.*\b(?:validated|approved|complete)\b", re.IGNORECASE)
PROXY = {"personal_status", "gender", "sex", "marital_status", "marriage", "foreign_worker", "race", "ethnicity",
         "religion", "nationality"}


def hits(model_id: str) -> list[tuple[Path, int, str]]:
    return [(p, n, ln.strip()) for p in extract.source_files(model_id)
            for n, ln in enumerate(p.read_text().splitlines(), 1) if PATTERNS.search(ln)]


def scan(model_id: str) -> list[Finding]:
    out = [
        Finding(id=f"SEC-{model_id}-{k}", model_id=model_id, area="prompt_injection", severity="high", ss123_principle="P2",
                description=f"Instruction-like text aimed at automated reviewers in {p.name} line {n}: {text[:160]}",
                evidence_ids=[extract.evidence_id(model_id, p.name, n, n)],
                recommendation="Remove the text; treat all source and documents as untrusted data, never as instructions.")
        for k, (p, n, text) in enumerate(hits(model_id), 1)
    ]
    out += [
        Finding(id=f"PROXY-{model_id}-{v}", model_id=model_id, area="fairness", severity="high", ss123_principle="P3",
                description=f"Protected-attribute proxy `{v}` is used by the model code: {text[:160]}",
                evidence_ids=[ev], recommendation="Justify the variable or remove it; test for disparate impact.")
        for v, ev, text in extract.collect(model_id)["proxy"]
    ]
    return out
