"""Deterministic claim verifier: no LLM, no network.

A claim is `supported` only if all of these hold:
  a. it cites at least one evidence id and every id exists (facts.evidence ids or metric keys);
  b. every code identifier it mentions exists in the facts (backticked words, plus unbackticked
     snake_case tokens, which are almost always variable or dataset names);
  c. every number in its text is traceable to facts.parameters, evidence excerpts, file line
     counts, model calls or metrics: equal within relative 1e-6, or the source rounded to the
     written number of decimals, or (for x%) the source fraction times 100.
`contradicted` = the claim names a numeric parameter and states a different value.
Unsupported and contradicted claims are kept and flagged, never dropped.
"""

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass

from modelproof.schemas import Claim, Facts

_NUM = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?!\w)")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TICKS = re.compile(r"`([^`\n]+)`")
_SNAKE = re.compile(r"(?<![\w.])([A-Za-z]+_[A-Za-z0-9_]*)(?!\w)(?!\.[A-Za-z]{1,4}\b)")
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_NOISE = re.compile(  # numbers that are labels, not claims: ids, dates, list numbering
    r"\b[A-Z]{2}-[A-Z]{2}-\d{3}\b|\bSS\d+/\d+\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    rf"|\b(?:in|since|from|by|during|of|FY)\s+(?:19|20)\d{{2}}\b|{_MONTH}\s+(?:\d{{1,2}},?\s+)?(?:19|20)\d{{2}}\b"
    r"|^\s*\d+[.)]\s|\(\d+\)",
    re.M | re.I,
)
_LINK = r"[`'\"]*\s*(?:[=:<>]+|is|of|at|was|equals?|set to|to)?\s*"


@dataclass
class _Ctx:
    ids: set[str]
    known: set[str]
    blob: str
    pool: list[float]
    params: dict[str, float]


def _parse(tok: str) -> tuple[float, int, bool, bool]:
    """-> (value, decimals written, is percent, is scientific)."""
    t = tok.rstrip("%").replace(",", "")
    mant = re.split("[eE]", t)[0]
    return (
        float(t),
        len(mant.split(".")[1]) if "." in mant else 0,
        tok.endswith("%"),
        "e" in t.lower(),
    )


def _leaves(o) -> Iterator:
    if isinstance(o, dict):
        for v in o.values():
            yield from _leaves(v)
    elif isinstance(o, list | tuple | set):
        for v in o:
            yield from _leaves(v)
    elif o is not None and not isinstance(o, bool):
        yield o


def _keys(o) -> Iterator[str]:
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(o, list | tuple):
        for v in o:
            yield from _keys(v)


def _nums(x) -> list[float]:
    if isinstance(x, int | float):
        return [float(x)] if math.isfinite(x) else []
    return [_parse(m.group())[0] for m in _NUM.finditer(str(x))]


def _scalar(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    m = _NUM.fullmatch(v.strip()) if isinstance(v, str) else None
    return _parse(m.group())[0] if m else None


def _context(facts: Facts, metrics: dict | None) -> _Ctx:
    m = metrics or {}
    texts = [e.excerpt for e in facts.evidence]
    texts += [str(c.get("text", "")) for c in facts.model_calls]
    texts += [str(x) for x in _leaves(m)]
    pool = [n for t in texts for n in _nums(t)]
    pool += [
        n for p in facts.parameters.values() for x in _leaves(p.get("value")) for n in _nums(x)
    ]
    pool += [float(f["n_lines"]) for f in facts.files if isinstance(f.get("n_lines"), int)]
    names = [
        *facts.variables_created,
        *facts.variables_used,
        *facts.dead_variables,
        *facts.datasets_read,
        *facts.datasets_written,
        *facts.dependencies,
        *facts.parameters,
        facts.model_id,
        facts.target or "",
        *texts,
        *_keys(m),
        *(str(f.get("path", "")) for f in facts.files),
        *(f"{e.id} {e.path}" for e in facts.evidence),
    ]
    params = {
        k.lower(): s
        for k, p in facts.parameters.items()
        if (s := _scalar(p.get("value"))) is not None
    }
    return _Ctx(
        ids={e.id for e in facts.evidence} | set(_keys(m)),
        known={t.lower() for s in names for t in _IDENT.findall(s)},
        blob="\n".join(s.lower() for s in names),
        pool=pool,
        params=params,
    )


def _close(v: float, dec: int, pct: bool, sci: bool, pool: list[float]) -> bool:
    half = 0.5 * 10**-dec * (1 + 1e-9)
    for s in pool:
        if math.isclose(v, s, rel_tol=1e-6, abs_tol=1e-12):
            return True
        if dec >= 1 and not sci and abs(v - s) <= half:
            return True
        if (
            pct
            and abs(s) <= 1.5
            and (math.isclose(v, s * 100, rel_tol=1e-6) or abs(v - s * 100) <= half)
        ):
            return True
    return False


def _ident_ok(span: str, x: _Ctx) -> bool:
    s = span.strip().lower()
    if not re.search(r"[a-z_]", s):
        return True  # pure number or symbol
    if _IDENT.fullmatch(s):
        return s in x.known
    return s in x.blob or all(t in x.known for t in _IDENT.findall(s))


def _contradictions(text: str, x: _Ctx) -> list[str]:
    out = []
    for name, val in x.params.items():
        if len(name) < 3:
            continue
        for m in re.finditer(rf"(?<!\w){re.escape(name)}{_LINK}({_NUM.pattern})", text, re.I):
            if not _close(*_parse(m.group(1)), [val]):
                out.append(f"`{name}` is {val:g} in the facts but the claim says {m.group(1)}")
    return out


def _check(c: Claim, x: _Ctx) -> Claim:
    why = []
    if not c.evidence_ids:
        why.append("no evidence ids")
    if bad := [i for i in c.evidence_ids if i not in x.ids]:
        why.append(f"unknown evidence ids: {bad}")
    plain = _TICKS.sub(" ", c.text)
    missing = [t for t in _TICKS.findall(c.text) if not _ident_ok(t, x)]
    missing += [t for t in _SNAKE.findall(plain) if t.lower() not in x.known]
    if missing:
        why.append(f"identifiers not found in facts: {sorted(set(missing))}")
    toks = [m.group() for m in _NUM.finditer(_NOISE.sub(" ", c.text))]
    if untraced := [t for t in toks if not _close(*_parse(t), x.pool)]:
        why.append(f"numbers not traceable to facts or metrics: {untraced}")
    if contra := _contradictions(c.text, x):
        return c.model_copy(update={"status": "contradicted", "reason": "; ".join(contra + why)})
    if why:
        return c.model_copy(update={"status": "unsupported", "reason": "; ".join(why)})
    return c.model_copy(update={"status": "supported", "reason": ""})


def verify(
    claims: list[Claim], facts: Facts, metrics: dict | None = None
) -> tuple[list[Claim], float]:
    """Grade every claim; return (graded copies, grounding = supported / total, 1.0 if no claims)."""
    x = _context(facts, metrics)
    out = [_check(c, x) for c in claims]
    return out, (sum(c.status == "supported" for c in out) / len(out) if out else 1.0)
