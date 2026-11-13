"""Render artifact JSON without executing or trusting its text."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from modelproof import config
from modelproof.report import charts


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _directory(model_id):
    root = Path(config.ARTIFACTS).resolve()
    path = (root / model_id).resolve()
    if path.parent != root:
        raise ValueError("model_id must be a single directory name")
    return path


def _render(template, output, **context):
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template(template).render(**context)
    output.write_text(html, encoding="utf-8")
    return output


def documentation(model_id):
    folder = _directory(model_id)
    doc = _read(folder / "documentation.json")
    facts = _read(folder / "facts.json") if (folder / "facts.json").exists() else {}
    evidence = {item["id"]: item for item in facts.get("evidence", [])}
    return _render("documentation.html.j2", folder / "documentation.html",
                   title="Model documentation", model_id=model_id, doc=doc, evidence=evidence)


def parity(model_id):
    folder = _directory(model_id)
    certificate = _read(folder / "parity_certificate.json")
    attempts = [_read(path) for path in sorted((folder / "redevelop").glob("attempt_*/certificate.json"))]
    return _render("parity.html.j2", folder / "parity_certificate.html",
                   title="Parity certificate", model_id=model_id, cert=certificate, attempts=attempts)


def _approvals(model_id):
    path = Path(config.ARTIFACTS) / "audit" / "audit_log.jsonl"
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        payload = event.get("payload", {})
        if event.get("model_id") == model_id and payload.get("decision") in {"approve", "reject"}:
            result.append({**payload, "reviewer": payload.get("reviewer", event.get("actor", "Unknown")),
                           "ts": payload.get("ts", event.get("ts", ""))})
    return result


def validation(model_id):
    folder = _directory(model_id)
    report = _read(folder / "validation_report.json")
    tests = report["results"]["tests"]
    images = {"Check summary": charts.to_base64(charts.rag_summary(tests))}
    data = report["results"].get("charts", {})
    if "roc" in data and {"fpr", "tpr"} <= data["roc"].keys():
        images["ROC"] = charts.to_base64(charts.roc(**{k: data["roc"][k] for k in ["fpr", "tpr"]}))
    if "calibration" in data:
        cal = data["calibration"]
        if "records" in cal:
            cal = {"predicted": [row["mean_predicted"] for row in cal["records"]],
                   "observed": [row["observed_rate"] for row in cal["records"]]}
        predicted = cal.get("predicted", cal.get("mean_predicted"))
        observed = cal.get("observed", cal.get("observed_rate"))
        if predicted is not None and observed is not None:
            images["Calibration"] = charts.to_base64(charts.calibration(predicted, observed))
    if "ks" in data:
        curve = data["ks"]
        images["KS"] = charts.to_base64(charts.ks(curve["score"], curve["good_cdf"], curve["bad_cdf"]))
    if "score_distribution" in data:
        images["Score distribution"] = charts.to_base64(charts.score_histogram(**data["score_distribution"]))
    return _render("validation.html.j2", folder / "validation_report.html",
                   title="Validation report", model_id=model_id, report=report,
                   images=images, approvals=_approvals(model_id))


def inventory():
    folder = Path(config.ARTIFACTS) / "inventory"
    rows = _read(folder / "inventory.json")
    return _render("inventory.html.j2", folder / "inventory.html",
                   title="Model inventory", model_id="All models", rows=rows)
