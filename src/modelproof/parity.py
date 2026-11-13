"""Five level parity harness: a rebuilt Python module against the R goldens of CR-PD-002."""
import builtins
import hashlib
import importlib.util
import platform
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy
import numpy as np
import numpy.exceptions
import numpy.linalg
import pandas
import pandas as pd
import pandas.errors
import statsmodels.tools.sm_exceptions

from modelproof import audit, config, data, sandbox
from modelproof.schemas import ParityCertificate, ParityLevel

MODEL_ID = "CR-PD-002"
COLS = ["ID", "pd", "score", "grade", "decision"]
SPLITS = ("dev", "holdout", "edge")
SRC = {"age_band": "AGE", "limit_band": "LIMIT_BAL"}  # raw numeric column behind a banded feature
ALIAS = {"Intercept": "(Intercept)", "const": "(Intercept)"}


NUM = re.compile(r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
IDENT = re.compile(r"[A-Za-z_][\w.]{0,39}")


def _exceptions(*modules) -> set[type]:
    return {c for m in modules for c in vars(m).values() if isinstance(c, type) and issubclass(c, BaseException)}


# compared by identity, never by __name__ / __module__, which generated code can set to anything
TRUSTED = _exceptions(builtins, pandas.errors, statsmodels.tools.sm_exceptions, numpy.linalg) | {numpy.exceptions.AxisError}


class SandboxError(ValueError):
    """Raised before executing code that breaks the allowlist; the message is built from the AST, not from data."""


def _describe(e: Exception, module_path: Path, known: set[str]) -> str:
    """What the LLM may be told about a failure of generated code that ran on real rows: the exception type if it comes from
    Python or a library, the line in the module, and a lookup name only if the golden tables or the dataset already contain
    it. Never message text, which the module controls."""
    if isinstance(e, SandboxError):
        return NUM.sub("#", str(e))[:200]
    tb, line = e.__traceback__, None
    while tb:
        line = tb.tb_lineno if Path(tb.tb_frame.f_code.co_filename) == module_path else line
        tb = tb.tb_next
    name = e.args[0] if isinstance(e, KeyError) and e.args else getattr(e, "name", None)
    out = next(c for c in type(e).__mro__ if c in TRUSTED).__name__  # nearest class we trust, e.g. a custom ValueError -> ValueError
    out += f" `{name}`" if isinstance(name, str) and name in known and IDENT.fullmatch(name) else ""
    return out + (f" at line {line}" if line else "")


def _gold() -> Path:
    return config.model_dir(MODEL_ID) / "golden"


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(module_path: Path):
    # defence in depth: the Redevelop agent already checked the code, but never exec anything that breaks the allowlist
    if bad := sandbox.check_code(module_path.read_text()):
        raise SandboxError("sandbox violations: " + "; ".join(bad[:5]))
    spec = importlib.util.spec_from_file_location(f"rebuilt_{_sha(module_path)[:12]}", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _coefs() -> dict[str, float]:
    c = _csv(_gold() / "coefficients.csv")
    return dict(zip(c.term, c.estimate, strict=True))


def score_fn(module_path: Path) -> Callable[[pd.DataFrame], pd.DataFrame]:
    """Raw rows -> ID, pd, score, grade, decision, using the golden coefficients and WoE tables."""
    mod, coefs, woe = _load(module_path), _coefs(), _csv(_gold() / "woe_tables.csv")
    return lambda df: mod.score(df.copy(), coefs, woe)[COLS].reset_index(drop=True)


def _merge(gold: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    m = gold.merge(pred, on="ID", how="outer", suffixes=("_g", "_p"), indicator=True)
    if (m._merge != "both").any():
        raise ValueError(f"{int((m._merge != 'both').sum())} IDs missing or extra in the rebuilt scores")
    return m


def _wrong(m: pd.DataFrame, pd_abs: float) -> pd.Series:
    return ((m.pd_g - m.pd_p).abs() > pd_abs) | (m.score_g != m.score_p) | (m.grade_g != m.grade_p) | (m.decision_g != m.decision_p)


def _localise(mod, rows: pd.DataFrame, dev: pd.DataFrame, cuts: pd.DataFrame, diffs: dict) -> dict:
    """Which feature's cut points explain the mismatching rows. Counts and cut points only, never rows."""
    out, f_bad, f_dev = {}, mod.build_features(rows.copy()), mod.build_features(dev.copy())
    for feat, grp in cuts.groupby("feature"):
        col = SRC.get(feat, feat)
        if col not in f_bad:
            continue
        x = pd.to_numeric(f_bad[col], errors="coerce")
        edges = np.unique(np.r_[grp.lower.dropna(), grp.upper.dropna()])
        edges = edges[np.isfinite(edges)]
        if x.isna().all() and "MISSING" in set(grp.bin_label):
            out[feat] = {"count": len(x), "nearest_cut": None, "pattern": "all missing (NaN) values"}
        elif x.notna().all() and x.isin(edges).all():
            base = pd.to_numeric(f_dev[col], errors="coerce").isin(edges).mean()
            if base < 0.5 or x.nunique() <= 2:  # sitting on a cut point is informative
                out[feat] = {"count": len(x), "nearest_cut": float(x.mode().iloc[0]), "pattern": "all exactly at cut point"}
    if not out and diffs["max_abs_score_diff"] == 1:
        out["score_rounding"] = {"count": len(rows), "pattern": "scores differ by exactly 1 (rounding rule)"}
    return out or {"unexplained": {"count": len(rows), **diffs}}


def save(cert: ParityCertificate, folder: Path, final: bool) -> None:
    """certificate.json in the attempt folder; the final attempt is also the artifact the UI and graph read."""
    (folder / "certificate.json").write_text(cert.model_dump_json(indent=2))
    if final:
        (config.artifact_dir(MODEL_ID) / "parity_certificate.json").write_text(cert.model_dump_json(indent=2))


def run(module_path: Path, attempt: int, run_id: str) -> ParityCertificate:
    pol = config.load_policy()
    tol, g = pol["parity"], _gold()
    raw = {s: data.load_cr_pd_002(s) for s in SPLITS}
    gold = {s: _csv(g / f"scored_{s}.csv") for s in SPLITS}
    gcoef, gwoe = _coefs(), _csv(g / "woe_tables.csv")
    known = {*gcoef, *COLS, *SRC.values(), *gwoe.columns, *gwoe.feature, *gwoe.bin_label, *raw["dev"].columns}
    levels: list[ParityLevel] = []
    summary: dict = {}
    st: dict = {}

    def level(lv: str, name: str, metric: str, tolerance: float, fn: Callable[[], tuple[bool, float, dict]]) -> None:
        try:
            ok, value, details = fn()
        except Exception as e:  # noqa: BLE001  any failure of generated code is a failed level, not a crash
            ok, value, details = False, -1.0, {"error": _describe(e, module_path, known)}
            summary.setdefault("error", details["error"])
        levels.append(ParityLevel(level=lv, name=name, passed=ok, metric=metric, value=float(value), tolerance=tolerance, details=details))

    try:
        mod = _load(module_path)
        mod_error = None
    except Exception as e:  # noqa: BLE001
        mod, mod_error = None, e

    def need() -> None:
        if mod_error:
            raise mod_error
        if not st:
            st.update({s: _merge(gold[s], mod.score(raw[s].copy(), gcoef, gwoe)[COLS]) for s in SPLITS})

    def l1():
        need()
        m = gwoe.merge(mod.woe_tables(raw["dev"].copy()), on=["feature", "bin_label"], how="outer", suffixes=("_g", "_p"), indicator="side")
        b = m[m.side == "both"]
        same = lambda c: np.isclose(b[f"{c}_g"].astype(float), b[f"{c}_p"].astype(float), rtol=0, atol=tol["coef_load_abs"], equal_nan=True)  # noqa: E731
        d = float((b.woe_g - b.woe_p).abs().max())
        odd = m[m.side != "both"]
        det = {"missing_or_extra_bins": len(odd), "extra_bins": int((odd.side == "right_only").sum()),
               # only golden labels are named; labels the module wrote are counted, never echoed
               "examples": [f"{r.feature}|{r.bin_label}|missing in rebuilt" for r in odd[odd.side == "left_only"].head(6).itertuples()],
               "count_mismatch_bins": int(((b.n_g != b.n_p) | (b.n_bad_g != b.n_bad_p)).sum()),
               "edge_mismatch_bins": int((~(same("lower") & same("upper")) | (b.closed_g != b.closed_p)).sum())}
        return d <= tol["coef_load_abs"] and not any(det.values()), d, det

    def l2():
        need()
        load = max(abs(float(s) - gcoef[t]) for t, s in pd.read_csv(g / "coefficients.csv", dtype=str).values)
        fit = {ALIAS.get(k, k): float(v) for k, v in mod.fit(raw["dev"].copy()).items()}
        missing, extra = sorted(set(gcoef) - set(fit)), len(set(fit) - set(gcoef))  # only golden names are echoed
        d = max(abs(fit[t] - gcoef[t]) for t in gcoef if t in fit) if not (missing or extra) else float("nan")
        det = {"golden_load_max_abs": load, "terms_missing": missing, "extra_terms": extra}
        return load <= tol["coef_load_abs"] and not (missing or extra) and d <= tol["coef_refit_abs"], -1.0 if (missing or extra) else d, det

    def both(a: str, b: str) -> pd.DataFrame:
        return pd.concat([st[a], st[b]])

    def l3():
        need()
        m = both("dev", "holdout")
        d, bad = float((m.pd_g - m.pd_p).abs().max()), int((m.score_g != m.score_p).sum())
        return d <= tol["pd_abs"] and bad == 0, d, {"score_mismatches": bad, "rows": len(m)}

    def l4():
        need()
        m = both("dev", "holdout")
        share = float(((m.grade_g == m.grade_p) & (m.decision_g == m.decision_p)).mean())
        return share >= 1.0, share, {"rows": len(m)}

    def l5():
        need()
        share = float((~_wrong(st["edge"], tol["pd_abs"])).mean())
        return share >= 1.0, share, {"rows": len(st["edge"])}

    level("L1", "Spec: bins and WoE tables", "max_abs_woe_diff", tol["coef_load_abs"], l1)
    level("L2", "Parameters: golden coefficients load, refit matches R", "max_abs_coef_refit_diff", tol["coef_refit_abs"], l2)
    level("L3", "Predictions: PD and score on dev and holdout", "max_abs_pd_diff", tol["pd_abs"], l3)
    level("L4", "Decisions: grade and decision on dev and holdout", "share_identical", 1.0, l4)
    level("L5", "Edge cases: all outputs on the edge file", "share_identical", 1.0, l5)

    if st:
        bad = {s: _wrong(st[s], tol["pd_abs"]) for s in SPLITS}
        if any(b.any() for b in bad.values()):
            ids = pd.concat([raw[s][raw[s].ID.isin(st[s].ID[bad[s]])] for s in SPLITS])
            m = pd.concat([st[s][bad[s]] for s in SPLITS])
            dpd, dsc = (m.pd_g - m.pd_p).abs().max(), (m.score_g - m.score_p).abs().max()  # NaN when the rebuild returned NaN
            diffs = {"max_abs_pd_diff": None if pd.isna(dpd) else float(dpd), "max_abs_score_diff": None if pd.isna(dsc) else int(dsc)}
            try:
                summary.update(_localise(mod, ids, raw["dev"], gwoe, diffs))
            except Exception as e:  # noqa: BLE001
                summary["unexplained"] = {"count": len(ids), **diffs, "localiser_error": type(e).__name__}
            summary["_rows"] = {s: int(bad[s].sum()) for s in SPLITS}

    hashes = {"python_module": _sha(module_path)}
    hashes |= {f"legacy_r:{p.name}": _sha(p) for p in sorted(config.model_dir(MODEL_ID).glob("*.R"))}
    hashes |= {f"input:cr_pd_002_{s}.csv": _sha(config.DATA_PROCESSED / f"cr_pd_002_{s}.csv") for s in SPLITS}
    hashes |= {f"golden:{p.name}": _sha(p) for p in sorted(g.iterdir()) if p.is_file()}
    versions = {"R": (g / "r_session.txt").read_text().splitlines()[0], "python": platform.python_version(),
                **{p: version(p) for p in ("pandas", "numpy", "statsmodels")}}
    cert = ParityCertificate(
        model_id=MODEL_ID, overall="PASS" if all(lv.passed for lv in levels) else "FAIL", levels=levels, hashes=hashes,
        versions=versions, mismatch_summary=summary, attempt=attempt, run_id=run_id, created_at=datetime.now(UTC))
    save(cert, module_path.parent, final=cert.overall == "PASS" or attempt >= pol["max_redevelop_attempts"])
    audit.append("parity.completed", {"overall": cert.overall, "attempt": attempt, "run_id": run_id,
                                      "levels": {lv.level: lv.passed for lv in levels}}, model_id=MODEL_ID, actor="parity")
    return cert
