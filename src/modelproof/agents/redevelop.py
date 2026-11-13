"""Redevelop agent: the LLM translates the R model to Python; code decides (sandbox, tests, five level parity).
The LLM sees R source, facts, a schema-only data dictionary and failure summaries, never a data row."""
import hashlib
import json
import shutil
from datetime import UTC, datetime

import pandas as pd
from pydantic import BaseModel

from modelproof import audit, config, data, extract, llm, parity, sandbox
from modelproof.schemas import ParityCertificate

MODEL_ID = "CR-PD-002"


class CodeBundle(BaseModel):
    module_code: str
    test_code: str
    notes: str = ""


def _brief(model_id: str, reviewer_comment: str) -> str:
    folder = config.model_dir(model_id)
    facts = extract.facts_for(model_id).model_dump(exclude={"evidence"})
    sources = [p for p in extract.source_files(model_id) if p.name in ("pd_model.R", "run_legacy.R")]
    golden = folder / "golden"
    shapes = {  # headers and coefficient names only, no values
        "coefficient_terms": pd.read_csv(golden / "coefficients.csv").term.tolist(),
        "woe_tables_columns": pd.read_csv(golden / "woe_tables.csv", nrows=0).columns.tolist(),
        "scored_columns": pd.read_csv(golden / "scored_dev.csv", nrows=0).columns.tolist()}
    tol = config.load_policy()["parity"]
    parts = [
        "Translate this R model. Legacy source files:",
        *[llm.untrusted(p.relative_to(config.ROOT).as_posix(), p.read_text()) for p in sources],
        "Extracted facts (JSON):", llm.untrusted(f"facts/{model_id}.json", json.dumps(facts, default=str)),
        "Raw input data dictionary (column: dtype, schema only):",
        json.dumps({c: str(t) for c, t in data.load_cr_pd_002("dev").dtypes.items()}),
        "Shapes of the R outputs your code is compared with (names only):", json.dumps(shapes),
        f"Parity rules: L1 bins and WoE tables identical (woe within {tol['coef_load_abs']}); L2 `fit` on the dev data "
        f"re-estimates the R coefficients within {tol['coef_refit_abs']}; L3 PD within {tol['pd_abs']} and identical scores "
        "on dev and holdout; L4 grade and decision 100% identical; L5 100% identical on an edge file of rows sitting exactly "
        "on and one unit either side of every cut point. All five must pass."]
    if reviewer_comment:
        parts.append(f"A human reviewer commented on the previous rebuild. Address this: {reviewer_comment}")
    return "\n".join(parts)


def _repair(prev: CodeBundle, cert: ParityCertificate, tests_out: str, reviewer_comment: str) -> str:
    def build(tail: str) -> str:
        levels = [lv.model_dump(include={"level", "passed", "metric", "value", "tolerance", "details"}) for lv in cert.levels]
        parts = ["Your previous attempt failed verification. Return a complete corrected CodeBundle.",
                 "Previous module:", llm.untrusted("previous/cr_pd_002.py", prev.module_code),
                 "Previous tests:", llm.untrusted("previous/test_cr_pd_002.py", prev.test_code),
                 "Parity levels (JSON):", json.dumps(levels, default=str),
                 "Mismatch summary (counts and nearest cut points, no data rows):", json.dumps(cert.mismatch_summary, default=str),
                 "Test output tail:", tail]
        if reviewer_comment:
            parts.append(f"Reviewer comment: {reviewer_comment}")
        return "\n".join(parts)

    msg = build(tests_out[-1500:])
    try:
        llm.assert_no_row_data(msg)
    except llm.RowDataError:  # a test printed a table: keep only the last line
        msg = build(tests_out.strip().splitlines()[-1] if tests_out.strip() else "")
    return msg


def _blocked(folder, attempt: int, run_id: str, summary: dict) -> ParityCertificate:
    """Certificate for an attempt that never reached the parity harness (sandbox violation or failing own tests)."""
    return ParityCertificate(
        model_id=MODEL_ID, overall="FAIL", levels=[], mismatch_summary=summary, attempt=attempt, run_id=run_id,
        hashes={"python_module": hashlib.sha256((folder / "cr_pd_002.py").read_bytes()).hexdigest()}, versions={},
        created_at=datetime.now(UTC))


def run(model_id: str = MODEL_ID, max_attempts: int | None = None, reviewer_comment: str = "") -> ParityCertificate:
    n_max = max_attempts or config.load_policy()["max_redevelop_attempts"]
    run_id, system = llm.run_id(), llm.load_prompt("redevelop")
    user = _brief(model_id, reviewer_comment)
    base = config.artifact_dir(model_id) / "redevelop"
    for attempt in range(1, n_max + 1):
        bundle = llm.structured(system, user, CodeBundle, "redevelop")
        folder = base / f"attempt_{attempt}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "cr_pd_002.py").write_text(bundle.module_code)
        (folder / "test_cr_pd_002.py").write_text(bundle.test_code)
        bad = sandbox.check_code(bundle.module_code) + [f"tests: {v}" for v in sandbox.check_tests(bundle.test_code)]
        if bad:
            out, cert = "sandbox violations:\n" + "\n".join(bad), _blocked(folder, attempt, run_id, {"sandbox_violations": bad})
        else:
            ok, out = sandbox.run_pytest(folder)
            cert = parity.run(folder / "cr_pd_002.py", attempt, run_id) if ok else _blocked(folder, attempt, run_id, {"tests_failed": True})
        (folder / "test_output.txt").write_text(out)
        parity.save(cert, folder, final=cert.overall == "PASS" or attempt == n_max)
        audit.append("redevelop.attempt", {"attempt": attempt, "overall": cert.overall, "levels": {lv.level: lv.passed for lv in cert.levels},
                                           "sandbox_violations": len(bad), "notes": bundle.notes[:300]}, model_id=model_id, actor="agent:redevelop")
        if cert.overall == "PASS":
            config.REBUILT.mkdir(parents=True, exist_ok=True)
            shutil.copy(folder / "cr_pd_002.py", config.REBUILT / "cr_pd_002.py")
            break
        user = _repair(bundle, cert, out, reviewer_comment)
    audit.append("redevelop.completed", {"overall": cert.overall, "attempts": cert.attempt}, model_id=model_id, actor="agent:redevelop")
    return cert
