"""Prompt injection scanner: instruction-like text in any source or document of a model folder."""
import re
from pathlib import Path

from modelproof.schemas import Finding

from modelproof import extract

PATTERNS = re.compile(
    r"ignore\s+(?:all|previous)\s+instructions|you\s+are\s+an\s+ai\b|system\s+prompt|classify\s+this\s+model\s+as|mark\s+.*\b(?:validated|approved|complete)\b",
    re.IGNORECASE)


def hits(model_id: str) -> list[tuple[Path, int, str]]:
    return [(p, n, ln.strip()) for p in extract.source_files(model_id) for n, ln in enumerate(p.read_text().splitlines(), 1) if PATTERNS.search(ln)]


def scan(model_id: str) -> list[Finding]:
    return [
        Finding(id=f"SEC-{model_id}-{k}", model_id=model_id, area="prompt_injection", severity="high", ss123_principle="P2",
                description=f"Instruction-like text aimed at automated reviewers in {p.name} line {n}: {text[:160]}",
                evidence_ids=[extract.evidence_id(model_id, p.name, n, n)],
                recommendation="Remove the text; treat all source and documents as untrusted data, never as instructions.")
        for k, (p, n, text) in enumerate(hits(model_id), 1)
    ]
