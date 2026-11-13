"""Write artifacts/metrics.json from files the pipeline produced, and refresh the README results table.

This script is the ONLY code that reads the ground truth in config.GOLD_DIR. Nothing is invented:
a number whose source file is missing is null and shows as "n/a" in the README table."""

import json
import re
from collections import Counter
from datetime import UTC, datetime

import yaml

from modelproof import audit, config, inventory, llm

TARGET = config.REBUILD_TARGET
README_MARKERS = ("<!-- RESULTS:START -->", "<!-- RESULTS:END -->")


def _json(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _jsonl(p):
    return (
        [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if p.exists()
        else []
    )


def _yaml(name):
    p = config.GOLD_DIR / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def _norm(x) -> str:
    return re.sub(r"\s+", " ", str(x).strip().lower())


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


# ------------------------------------------------------------------ runtime and LLM usage
def _runs() -> dict[str, dict]:
    """Latest 'live' run (some LLM call was not cached) and latest 'replay' run (all calls cached)."""
    found: dict[str, dict] = {}
    root = config.ARTIFACTS / "runs"
    for d in sorted(root.iterdir()) if root.exists() else []:
        usage, timings = _jsonl(d / "llm_usage.jsonl"), _jsonl(d / "timings.jsonl")
        if usage:
            found["replay" if all(u["cache_hit"] for u in usage) else "live"] = {
                "run_id": d.name, "usage": usage, "timings": timings,
            }  # fmt: skip
    return found


def _runtime(timings: list[dict]) -> dict:
    per_model, per_stage, per_ms = Counter(), Counter(), {}
    for t in timings:
        per_model[t["model_id"]] += t["seconds"]
        per_stage[t["stage"]] += t["seconds"]
        per_ms.setdefault(t["model_id"], Counter())[t["stage"]] += t["seconds"]
    r = lambda c: {k: round(v, 2) for k, v in c.items()}  # noqa: E731
    return {
        "total_s": round(sum(per_model.values()), 2),
        "per_model_s": r(per_model),
        "per_stage_s": r(per_stage),
        "per_model_stage_s": {m: r(c) for m, c in per_ms.items()},
    }


def _llm_usage(usage: list[dict]) -> dict:
    per: dict[str, Counter] = {}
    for u in usage:
        c = per.setdefault(u.get("model_id") or "unattributed", Counter())
        c["calls"] += 1
        c["input_tokens"] += u["input_tokens"]
        c["output_tokens"] += u["output_tokens"]
        c["cost_usd"] += u["cost_usd"]
        c["cache_hits"] += int(u["cache_hit"])
    per_model = {m: {**c, "cost_usd": round(c["cost_usd"], 4)} for m, c in per.items()}
    tot = {
        k: sum(c[k] for c in per.values())
        for k in ("calls", "input_tokens", "output_tokens", "cache_hits")
    }
    return {
        "per_model": per_model,
        "total": {**tot, "cost_usd": round(sum(c["cost_usd"] for c in per.values()), 4)},
    }


# ------------------------------------------------------------------ accuracy against ground truth
# Gold inventory is flat per model (eval/gold/inventory_gold.yaml). Fields that code computes are scored
# apart from fields the LLM proposes, so the two accuracies are never blended.
DETERMINISTIC = {
    "language": "platform_language",
    "upstream_models": "upstream_models",
    "downstream_models": "downstream_models",
    "documentation_status": "documentation_status",
}


def _names(rec: dict) -> list[str]:
    return [f["name"] for f in rec["features"]]


def _field_ok(key: str, exp, rec: dict) -> bool:
    if (
        key == "features"
    ):  # every gold feature appears (substring either way) among the predicted features
        return all(any(_vm(e, n) for n in _names(rec)) for e in exp)
    if key == "target":  # the target column is named in the target definition
        return _norm(exp) in _norm(rec["target_definition"])
    got = rec.get(DETERMINISTIC.get(key, key))
    if isinstance(exp, list):
        return {_norm(x) for x in exp} == {_norm(x) for x in (got or [])}
    return _norm(exp) == _norm(got)


def _inventory_accuracy(recs: dict[str, dict], gold: dict | None) -> dict | None:
    if not gold:
        return None
    out: dict = {"per_model": {}}
    for section in ("deterministic", "llm"):
        ok = tot = 0
        for mid, g in gold.items():
            keys = [k for k in g if (k in DETERMINISTIC) == (section == "deterministic")]
            res = {k: bool(mid in recs and _field_ok(k, g[k], recs[mid])) for k in keys}
            out["per_model"].setdefault(mid, {})[section] = res
            ok, tot = ok + sum(res.values()), tot + len(res)
        out[section] = {"correct": ok, "total": tot, "accuracy": _ratio(ok, tot)}
    return out


def _vm(a, b) -> bool:
    a, b = _norm(a), _norm(b)
    return bool(a and b) and (a in b or b in a)


def _evidence(mid: str) -> dict[str, dict]:
    return {
        e["id"]: e for e in (_json(config.ARTIFACTS / mid / "facts.json") or {}).get("evidence", [])
    }


def _at(ev: dict | None, file: str, line: int) -> bool:
    return bool(ev and ev["path"] == file and ev["line_start"] <= line <= ev["line_end"])


def _drift_matches(g: dict, d: dict, ev: dict[str, dict]) -> bool:
    """Same location (both evidence lines cover the gold doc and code lines) or same values."""
    where = _at(ev.get(d["doc_evidence_id"]), g["doc_file"], g["doc_line"]) and _at(
        ev.get(d["code_evidence_id"]), g["code_file"], g["code_line"]
    )
    code_gold = g.get("code_value", g.get("true_value", ""))
    return where or (_vm(g["doc_value"], d["doc_value"]) and _vm(code_gold, d["code_value"]))


def _drift_scores(recs: dict[str, dict], gold: list | None) -> dict | None:
    if gold is None:
        return None
    evs = {mid: _evidence(mid) for mid in recs}
    pred = [(mid, d) for mid, r in recs.items() for d in r["doc_code_drifts"] if d["verified"]]
    hit_gold, tp = set(), 0
    for mid, d in pred:
        hits = [g["id"] for g in gold if g["model_id"] == mid and _drift_matches(g, d, evs[mid])]
        hit_gold.update(hits)
        tp += bool(hits)
    return {
        "predicted": len(pred), "gold": len(gold), "true_positives": tp, "gold_found": len(hit_gold),
        "precision": _ratio(tp, len(pred)), "recall": _ratio(len(hit_gold), len(gold)),
    }  # fmt: skip


def _mentions(word: str, texts: list[str]) -> bool:
    pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9])", re.I)
    return any(pat.search(t) for t in texts)


def _risk_detected(r: dict, rec: dict, facts: dict, report: dict) -> bool:
    kind, desc = r["kind"], r["description"]
    word = re.match(r"[\w$]+", desc).group(0)  # gold descriptions start with the variable name
    flags = [f"{f['area']} {f['description']}" for f in rec["security_flags"]]
    notes = (
        flags
        + rec["limitations"]
        + [f"{d['field']} {d['doc_value']} {d['code_value']}" for d in rec["doc_code_drifts"]]
    )
    if kind == "prompt_injection":
        return any(file_name in f for f in flags for file_name in [r["file"].rsplit("/", 1)[-1]])
    if kind == "dependency":
        return any(
            i in rec["upstream_models"] for i in re.findall(r"[A-Z]{2}-[A-Z]{2}-\d{3}", desc)
        )
    if kind == "undocumented_model":
        return rec["documentation_status"] == "missing"
    if kind == "dead_variable":
        return word.lower() in {v.lower() for v in facts.get("dead_variables", [])} or _mentions(
            word, notes
        )
    if (
        kind == "stale_comment"
    ):  # the extractor records the comment's number as `<constant>_comment`
        name = re.match(r"[A-Za-z _]+", r["anchor"]).group(0).strip().replace(" ", "_").lower()
        return any(
            k.lower().endswith("_comment") and k.lower().startswith(name)
            for k in facts.get("parameters", {})
        )
    findings = [f"{f['area']} {f['description']}" for f in report.get("findings", [])] + list(
        (report.get("narrative") or {}).values()
    )
    return _mentions(word, notes + findings)  # proxy_variable, protected_attribute_used


def _risk_scores(recs: dict[str, dict], gold: list | None) -> dict | None:
    if gold is None:
        return None
    report = _json(config.ARTIFACTS / TARGET / "validation_report.json") or {}
    res = {
        r["id"]: bool(r["model_id"] in recs and _risk_detected(
            r, recs[r["model_id"]], _json(config.ARTIFACTS / r["model_id"] / "facts.json") or {},
            report if r["model_id"] == TARGET else {},
        ))
        for r in gold
    }  # fmt: skip
    kinds = Counter(r["kind"] for r in gold)
    found = Counter(r["kind"] for r in gold if res[r["id"]])
    return {
        "detected": sum(res.values()), "total": len(res), "per_risk": res,
        "per_kind": {k: f"{found[k]}/{n}" for k, n in kinds.items()},
    }  # fmt: skip


# ------------------------------------------------------------------ artifact summaries
def _grounding(recs) -> dict:
    docs = {
        m: (_json(config.ARTIFACTS / m / "documentation.json") or {}).get("grounding_score")
        for m in recs
    }
    rep = _json(config.ARTIFACTS / TARGET / "validation_report.json") or {}
    claims = rep.get("claims") or []
    ok = sum(c["status"] == "supported" for c in claims)
    vals = [v for v in docs.values() if v is not None]
    return {
        "documentation": docs,
        "documentation_mean": round(sum(vals) / len(vals), 4) if vals else None,
        "validation_narrative": _ratio(ok, len(claims)),
    }


def _parity() -> dict | None:
    cert = _json(config.ARTIFACTS / TARGET / "parity_certificate.json")
    if not cert:
        return None
    attempts = len(list((config.ARTIFACTS / TARGET / "redevelop").glob("attempt_*")))
    return {
        "overall": cert["overall"], "final_attempt": cert["attempt"], "attempt_dirs": attempts,
        "self_heal_attempts": max(0, attempts - 1) if attempts else None,
        "levels": {x["level"]: {"name": x["name"], "passed": x["passed"], "value": x["value"],
                                "tolerance": x["tolerance"]} for x in cert["levels"]},
    }  # fmt: skip


def _validation() -> dict | None:
    rep = _json(config.ARTIFACTS / TARGET / "validation_report.json")
    if not rep:
        return None
    tests = rep["results"]["tests"]
    return {
        "rating": rep["rating"], "n_tests": len(tests), "rag_mix": dict(Counter(t["rag"] for t in tests)),
        "n_findings": len(rep["findings"]), "findings_by_severity": dict(Counter(f["severity"] for f in rep["findings"])),
    }  # fmt: skip


def _monitoring() -> dict | None:
    mon = _json(config.ARTIFACTS / TARGET / "monitoring.json")
    return mon and {
        "trigger_month": mon["trigger_month"],
        "months": len(mon["points"]),
        "simulated": mon["simulated"],
    }


def collect() -> dict:
    recs = {r.model_id: r.model_dump(mode="json") for r in inventory.load()}
    runs = _runs()
    live, replay = runs.get("live"), runs.get("replay")
    approvals = [a for r in recs.values() for a in r["approvals"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "llm": {"provider": llm._provider(), "model": llm._model_name(), "mode_note": "tokens and cost come from the live run"},
        "runs": {k: v["run_id"] for k, v in runs.items()},
        "runtime": {k: _runtime(v["timings"]) for k, v in runs.items() if v["timings"]},
        "llm_usage": _llm_usage(live["usage"]) if live else None,
        "replay_cache_hits": _ratio(sum(u["cache_hit"] for u in replay["usage"]), len(replay["usage"])) if replay else None,
        "inventory": {m: {"tier": r["risk_tier"], "documentation_status": r["documentation_status"], "status": r["status"],
                          "n_drifts": len(r["doc_code_drifts"]), "n_security_flags": len(r["security_flags"])}
                      for m, r in recs.items()},
        "inventory_accuracy": _inventory_accuracy(recs, _yaml("inventory_gold.yaml")),
        "drift_detection": _drift_scores(recs, _yaml("seeded_drifts.yaml")),
        "seeded_risks": _risk_scores(recs, _yaml("seeded_risks.yaml")),
        "grounding": _grounding(recs),
        "parity": _parity(),
        "validation": _validation(),
        "monitoring": _monitoring(),
        "governance": {
            "audit_entries": len(audit.read()), "audit_chain_ok": audit.verify_chain(),
            "approvals_human": sum(not a["auto"] for a in approvals), "approvals_auto": sum(a["auto"] for a in approvals),
        },
    }  # fmt: skip


# ------------------------------------------------------------------ README table
def _fmt(v, pct=False, unit="") -> str:
    if v is None:
        return "n/a"
    return f"{v:.0%}" if pct else f"{v}{unit}"


def results_table(m: dict) -> str:
    """Markdown rows, every value read from metrics.json (n/a when the source file was missing)."""
    g = lambda *ks: _dig(m, ks)  # noqa: E731
    live = g("runtime", "live", "total_s")
    rows = [
        ("Models inventoried", len(m["inventory"])),
        ("Inventory accuracy, deterministic fields", _fmt(g("inventory_accuracy", "deterministic", "accuracy"), True)),
        ("Inventory accuracy, LLM fields", _fmt(g("inventory_accuracy", "llm", "accuracy"), True)),
        ("Seeded doc vs code drift: precision / recall (seeded)", f"{_fmt(g('drift_detection', 'precision'), True)} / {_fmt(g('drift_detection', 'recall'), True)}"),
        ("Seeded risks detected (seeded)", f"{g('seeded_risks', 'detected')} of {g('seeded_risks', 'total')}" if g("seeded_risks") else "n/a"),
        ("Documentation grounding (mean)", _fmt(g("grounding", "documentation_mean"), True)),
        ("Parity certificate", _fmt(g("parity", "overall"))),
        ("Parity levels passed", f"{sum(x['passed'] for x in g('parity', 'levels').values())} of {len(g('parity', 'levels'))}" if g("parity") else "n/a"),
        ("Self-heal attempts", _fmt(g("parity", "self_heal_attempts"))),
        ("Validation tests / RAG mix", f"{g('validation', 'n_tests')} / {g('validation', 'rag_mix')}" if g("validation") else "n/a"),
        ("Validation rating", _fmt(g("validation", "rating"))),
        ("Monitoring trigger month (simulated)", _fmt(g("monitoring", "trigger_month")) if g("monitoring") else "n/a"),
        ("Pipeline wall time, live run", _fmt(live, unit=" s")),
        ("Pipeline wall time, replay run", _fmt(g("runtime", "replay", "total_s"), unit=" s")),
        ("LLM tokens in / out (live run)", f"{g('llm_usage', 'total', 'input_tokens')} / {g('llm_usage', 'total', 'output_tokens')}" if g("llm_usage") else "n/a"),
        ("LLM cost, whole estate (live run)", f"${g('llm_usage', 'total', 'cost_usd')}" if g("llm_usage") else "n/a"),
        ("Audit log entries / chain intact", f"{g('governance', 'audit_entries')} / {g('governance', 'audit_chain_ok')}"),
        ("Gate approvals: human / auto", f"{g('governance', 'approvals_human')} / {g('governance', 'approvals_auto')}"),
    ]  # fmt: skip
    return "| Metric | Value |\n| --- | --- |\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)


def _dig(d, keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def update_readme(m: dict) -> bool:
    p = config.ROOT / "README.md"
    a, b = README_MARKERS
    if not p.exists() or a not in (t := p.read_text(encoding="utf-8")) or b not in t:
        return False
    head, rest = t.split(a, 1)
    p.write_text(f"{head}{a}\n{results_table(m)}\n{b}{rest.split(b, 1)[1]}", encoding="utf-8")
    return True


def main():
    m = collect()
    out = config.ARTIFACTS / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    update_readme(m)
    return out


if __name__ == "__main__":
    print(f"wrote {main()}")
