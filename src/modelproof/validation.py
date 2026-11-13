"""Deterministic validation of the rebuilt PD model against fixed team policy."""

import json
from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_curve

from modelproof import audit, config, data, fairness, metrics
from modelproof.schemas import CheckResult, ValidationResults


def scored_rows(frame: pd.DataFrame, score_fn: Callable) -> pd.DataFrame:
    """Join scores by ID, rejecting incomplete or ambiguous scoring outputs."""
    required = {"ID", "pd", "score", "grade", "decision"}
    if frame.empty or "ID" not in frame or frame.ID.isna().any() or frame.ID.duplicated().any():
        raise ValueError("Input must have nonempty, unique, non-null IDs")
    scores = score_fn(frame.copy())
    if not required.issubset(scores) or scores.ID.isna().any() or scores.ID.duplicated().any():
        raise ValueError("Scoring output requires unique IDs and all contract columns")
    if set(scores.ID) != set(frame.ID):
        raise ValueError("Scoring output IDs must exactly match input IDs")
    if not np.isfinite(scores[["pd", "score"]].to_numpy(dtype=float)).all():
        raise ValueError("Scores must be finite")
    if not scores["pd"].between(0, 1).all():
        raise ValueError("Predicted default probabilities must lie in [0,1]")
    if scores.decision.isna().any() or scores.grade.isna().any():
        raise ValueError("Scoring decisions and grades violate the contract")
    raw = frame.drop(columns=list((required - {"ID"}) & set(frame)))
    return raw.merge(scores, on="ID", validate="one_to_one", sort=False)


def _rag(value: float, thresholds: dict, higher: bool = False) -> str:
    if value is None or not np.isfinite(value):
        return "amber"
    if higher:
        return "green" if value >= thresholds["green"] else "amber" if value >= thresholds["amber"] else "red"
    return "green" if value < thresholds["green"] else "amber" if value < thresholds["amber"] else "red"


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records"))


def rating(tests: list[CheckResult]) -> str:
    rule = config.load_policy()["rating_rule"]
    reds = sum(test.rag == "red" for test in tests)
    concerns = sum(test.rag in {"red", "amber"} for test in tests)
    if reds >= rule["not_fit_if_red_at_least"]:
        return "Not fit"
    if concerns >= rule["conditions_if_red_or_amber_at_least"] or not tests:
        return "Fit with conditions"
    return "Fit for use"


def run_suite(model_id, dev: pd.DataFrame, holdout: pd.DataFrame, score_fn, features: list[str]) -> ValidationResults:
    """Score independent splits, compute metrics, persist evidence and audit event."""
    policy = config.load_policy()
    if set(dev.ID) & set(holdout.ID):
        raise ValueError("Development and holdout IDs overlap")
    if not features or len(set(features)) != len(features):
        raise ValueError("Provide unique raw feature names")
    if {"ID", "DEFAULT", "pd", "score", "grade", "decision"} & set(features):
        raise ValueError("Identifiers, targets and scoring outputs cannot be benchmark features")
    for frame in (dev, holdout):
        if not set(features).issubset(frame):
            raise ValueError("Missing requested raw features")
        if not frame.DEFAULT.isin([0, 1]).all() or frame.DEFAULT.nunique() != 2:
            raise ValueError("Each validation split needs both binary outcome classes")
    d, h = scored_rows(dev, score_fn), scored_rows(holdout, score_fn)
    h["AGE_BAND"] = data.age_band(h.AGE)
    tests: list[CheckResult] = []
    tables = {}

    def add(name, area, value, rag="green", threshold="Descriptive metric; no decision threshold in policy", details=None):
        finite = value is not None and np.isfinite(value)
        tests.append(CheckResult(test=name, area=area, value=float(value) if finite else None,
                                 threshold=threshold, rag=rag if finite else "amber",
                                 ss123_principle="P3" if area in {"conceptual", "data_quality", "implementation"} else "P4",
                                 details=details or {}))

    gd, gh = metrics.gini(d.DEFAULT, d["pd"]), metrics.gini(h.DEFAULT, h["pd"])
    for split, frame, value in (("dev", d, gd), ("holdout", h, gh)):
        add(f"gini_{split}", "discrimination", value, _rag(value, policy["gini"], True),
            str(policy["gini"]), {"bootstrap_ci": list(metrics.bootstrap_ci(metrics.gini, frame.DEFAULT, frame["pd"]))})
    add("auc_holdout", "discrimination", metrics.auc(h.DEFAULT, h["pd"]))
    add("ks_holdout", "discrimination", metrics.ks(h.DEFAULT, h["pd"]))
    drop = (gd - gh) / gd if gd > 0 else np.nan
    add("gini_drop_rel", "discrimination", drop, _rag(drop, policy["gini_drop_rel"]), str(policy["gini_drop_rel"]))
    stat, pvalue = metrics.hosmer_lemeshow(h.DEFAULT, h["pd"])
    add("hosmer_lemeshow_p", "calibration", pvalue,
        "green" if pvalue >= policy["hosmer_lemeshow_p"]["green"] else "red",
        str(policy["hosmer_lemeshow_p"]), {"statistic": float(stat)})
    add("brier", "calibration", metrics.brier(h.DEFAULT, h["pd"]))
    tables["calibration"] = _records(metrics.calibration_table(h.DEFAULT, h["pd"]))
    jeff = metrics.jeffreys_by_grade(h, alpha=policy["jeffreys"]["alpha"])
    failures = int(jeff["fail"].sum())
    jp = policy["jeffreys"]
    add("jeffreys_failures", "calibration", failures,
        "red" if failures >= jp["red_failures"] else "amber" if failures >= jp["amber_failures"] else "green", str(jp))
    tables["jeffreys"] = _records(jeff)
    sp = metrics.psi(d.score, h.score)
    add("score_psi", "stability", sp, _rag(sp, policy["psi"]), str(policy["psi"]))
    cs = metrics.csi(dev, holdout, features)
    tables["csi"] = [{"feature": key, "csi": value} for key, value in cs.items()]
    for key, value in cs.items():
        add(f"csi_{key}", "stability", value, _rag(value, policy["csi"]), str(policy["csi"]))
    iv_rows = []
    for feature in features:
        series = dev[feature]
        binned = pd.qcut(series, 10, duplicates="drop") if pd.api.types.is_numeric_dtype(series) and series.nunique() > 1 else series
        _, iv = metrics.woe_iv(binned, dev.DEFAULT)
        iv_rows.append({"feature": feature, "iv": iv})
        add(f"iv_{feature}", "conceptual", iv, "amber" if iv < policy["iv_useless"] else "green", f">= {policy['iv_useless']}")
    tables["iv"] = iv_rows
    numeric = dev[features].select_dtypes(include="number")
    vif_values = metrics.vif(numeric) if len(numeric.columns) and not numeric.isna().any().any() else {}
    if not vif_values:
        add("vif", "conceptual", None, details={"reason": "No complete numeric feature matrix; VIF unavailable"})
    for key, value in vif_values.items():
        add(f"vif_{key}", "conceptual", value, "red" if np.isinf(value) else _rag(value, policy["vif"]), str(policy["vif"]), {"infinite": bool(np.isinf(value))})
        if np.isinf(value):
            tests[-1].rag = "red"
    add("grade_hhi", "conceptual", metrics.hhi(h.grade))
    if len(numeric.columns) != len(features):
        add("challenger_gini_gap", "benchmark", None, details={"reason": "Challenger requires numeric raw features"})
    else:
        challenger = HistGradientBoostingClassifier(random_state=42, max_iter=100).fit(dev[features], dev.DEFAULT)
        gap = metrics.gini(holdout.DEFAULT, challenger.predict_proba(holdout[features])[:, 1]) - gh
        add("challenger_gini_gap", "benchmark", gap, _rag(gap, policy["benchmark_gini_gap"]), str(policy["benchmark_gini_gap"]))
    for feature in ("BILL_AMT1", "LIMIT_BAL"):
        for factor in (0.9, 1.1):
            shock = holdout.copy()
            shock[feature] = shock[feature] * factor
            shifted = scored_rows(shock, score_fn).set_index("ID").score.reindex(h.ID)
            shift = float(np.abs(shifted.to_numpy() - h.score.to_numpy()).mean())
            add(f"sensitivity_{feature}_{factor}", "sensitivity", shift,
                _rag(shift, policy["sensitivity_mean_shift"]), str(policy["sensitivity_mean_shift"]))
    h["approved"] = h.decision.eq("approve").astype(int)
    fair = fairness.report(h, "DEFAULT", "approved", "pd", list(data.PROTECTED))
    tables["fairness"] = fair["groups"]
    for key, prefix, higher in (("worst_dp_ratio", "dp_ratio", True), ("worst_eod", "eod", False)):
        value = fair[key]
        thresholds = {level: policy["fairness"][f"{prefix}_{level}"] for level in ("green", "amber")}
        add(key, "fairness", value, _rag(value, thresholds, higher), str(thresholds),
            {"note": "Approval is the positive decision; DEFAULT=1 denotes default. Rates require contextual interpretation."})
    for column in holdout:
        value = float(holdout[column].isna().mean())
        add(f"missing_{column}", "data_quality", value, _rag(value, policy["missing_rate"]), str(policy["missing_rate"]))
    for column, valid in (("AGE", holdout.AGE.between(21, 79)), ("SEX", holdout.SEX.isin([1, 2]))):
        count = int((~valid).sum())
        add(f"range_{column}", "data_quality", count, "red" if count else "green", "No out-of-range values", {"range": "21..79" if column == "AGE" else "{1,2}"})
    out = config.artifact_dir(model_id)
    cert_path = out / "parity_certificate.json"
    status = json.loads(cert_path.read_text(encoding="utf-8"))["overall"] if cert_path.exists() else "missing"
    if status not in {"PASS", "FAIL", "missing"}:
        raise ValueError("Invalid parity certificate status")
    add("parity", "implementation", float(status == "PASS"), {"PASS": "green", "FAIL": "red", "missing": "amber"}[status], "Certificate overall PASS", {"status": status})
    fpr, tpr, _ = roc_curve(h.DEFAULT, h["pd"])
    order = h.groupby("pd").DEFAULT.agg(["count", "sum"])
    good = (order["count"] - order["sum"]).cumsum() / h.DEFAULT.eq(0).sum()
    bad = order["sum"].cumsum() / h.DEFAULT.eq(1).sum()
    edges = np.histogram_bin_edges(np.concatenate([d.score.to_numpy(), h.score.to_numpy()]), bins=20)
    counts_d, _ = np.histogram(d.score, bins=edges)
    counts_h, _ = np.histogram(h.score, bins=edges)
    charts = {"roc": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
              "ks": {"score": order.index.tolist(), "good_cdf": good.tolist(), "bad_cdf": bad.tolist()},
              "score_distribution": {"edges": edges.tolist(), "dev": counts_d.tolist(), "holdout": counts_h.tolist()},
              "calibration": {"records": tables["calibration"]}}
    result = ValidationResults(model_id=model_id, tests=tests, tables=tables, charts=charts)
    (out / "validation_results.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    audit.append("validation_suite_run", {"tests": len(tests), "rating": rating(tests), "artifact": str(out / "validation_results.json")}, model_id=model_id)
    return result
