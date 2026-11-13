"""Test-only reference translation of pd_model.R (B5 interface). Lets the tests prove the goldens are reachable and
gives the mocked Redevelop agent a 'fixed' answer. The real rebuild is always written by the agent at runtime."""
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.special import expit

PAY = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
CUT_UTIL, CUT_PAYR, CUT_AGE, CUT_LIMIT = [0, 0.25, 0.5, 0.75, 1], [0.02, 0.1, 0.5, 1], [25, 30, 40, 50], [50000, 100000, 200000]
PDO, BASE_SCORE, BASE_ODDS, CUTOFF = 20, 600, 25, 560
GRADE_CUTS = [500, 520, 540, 560, 565, 570]
WOE_VARS = {"util": "woe_util", "pay_ratio": "woe_pay_ratio", "n_delinq": "woe_n_delinq", "worst_status": "woe_worst_status",
            "age_band": "woe_age", "limit_band": "woe_limit"}
SRC = {"util": "util", "pay_ratio": "pay_ratio", "n_delinq": "n_delinq", "worst_status": "worst_status", "age_band": "AGE", "limit_band": "LIMIT_BAL"}


def fmt(x: float) -> str:
    return "Inf" if x == math.inf else "-Inf" if x == -math.inf else format(x, ".15g")


def spec(feature: str, cuts: list, closed: str) -> list[tuple]:
    lo, hi = [-math.inf, *cuts], [*cuts, math.inf]
    lab = [f"({fmt(a)},{fmt(b)}]" if closed == "right" else f"[{fmt(a)},{fmt(b)})" for a, b in zip(lo, hi, strict=True)]
    return [(feature, ll, a, b, closed) for ll, a, b in zip(lab, lo, hi, strict=True)]


SPECS = (spec("util", CUT_UTIL, "right") + spec("pay_ratio", CUT_PAYR, "left") + [("pay_ratio", "MISSING", np.nan, np.nan, "none")]
         + [("n_delinq", "0", 0, 0, "both"), ("n_delinq", "1", 1, 1, "both"), ("n_delinq", "2-3", 2, 3, "both"), ("n_delinq", "4+", 4, math.inf, "left")]
         + [("worst_status", "<=0", -math.inf, 0, "right"), ("worst_status", "1", 1, 1, "both"), ("worst_status", "2", 2, 2, "both"),
            ("worst_status", "3+", 3, math.inf, "left")]
         + spec("age_band", CUT_AGE, "left") + spec("limit_band", CUT_LIMIT, "left"))
SPEC = pd.DataFrame(SPECS, columns=["feature", "bin_label", "lower", "upper", "closed"])


def labels(feature: str) -> list[str]:
    return SPEC.bin_label[SPEC.feature == feature].tolist()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "ID": df.ID.to_numpy(), "util": (df.BILL_AMT1 / df.LIMIT_BAL).to_numpy(),
        "pay_ratio": (df.PAY_AMT1 / df.BILL_AMT1).where(df.BILL_AMT1 > 0).to_numpy(),
        "n_delinq": (df[PAY] > 0).sum(axis=1).to_numpy(), "worst_status": df[PAY].max(axis=1).to_numpy(),
        "AGE": df.AGE.to_numpy(), "LIMIT_BAL": df.LIMIT_BAL.to_numpy()})


def apply_bins(f: pd.DataFrame) -> pd.DataFrame:
    pick = lambda feat, idx: np.array(labels(feat))[idx]  # noqa: E731
    pr = f.pay_ratio.to_numpy()
    n, w = f.n_delinq.to_numpy(), f.worst_status.to_numpy()
    return pd.DataFrame({
        "ID": f.ID.to_numpy(),
        "util": pick("util", np.searchsorted(CUT_UTIL, f.util.to_numpy(), side="left")),  # right closed
        "pay_ratio": np.where(np.isnan(pr), "MISSING", pick("pay_ratio", np.searchsorted(CUT_PAYR, np.nan_to_num(pr), side="right"))),
        "n_delinq": np.select([n == 0, n == 1, n <= 3], ["0", "1", "2-3"], "4+"),
        "worst_status": np.select([w <= 0, w == 1, w == 2], ["<=0", "1", "2"], "3+"),
        "age_band": pick("age_band", np.searchsorted(CUT_AGE, f.AGE.to_numpy(), side="right")),
        "limit_band": pick("limit_band", np.searchsorted(CUT_LIMIT, f.LIMIT_BAL.to_numpy(), side="right"))})


def woe_tables(dev: pd.DataFrame) -> pd.DataFrame:
    bins, out = apply_bins(build_features(dev)), []
    for feat, s in SPEC.groupby("feature", sort=False):
        s = s.copy()
        s["n"] = s.bin_label.map(bins[feat].value_counts()).fillna(0).astype(int).to_numpy()
        s["n_bad"] = s.bin_label.map(dev.DEFAULT.groupby(bins[feat].to_numpy()).sum()).fillna(0).astype(int).to_numpy()
        ng = s.n - s.n_bad
        z = ((s.n_bad == 0) | (ng == 0)) * 0.5
        s["woe"] = np.log(((ng + z) / ng.sum()) / ((s.n_bad + z) / s.n_bad.sum()))
        out.append(s)
    return pd.concat(out, ignore_index=True)


def _woe_matrix(df: pd.DataFrame, woe: pd.DataFrame) -> pd.DataFrame:
    bins = apply_bins(build_features(df))
    return pd.DataFrame({v: bins[f].map(woe[woe.feature == f].set_index("bin_label").woe) for f, v in WOE_VARS.items()})


def fit(dev: pd.DataFrame) -> dict[str, float]:
    X = sm.add_constant(_woe_matrix(dev, woe_tables(dev)), has_constant="add")
    p = sm.GLM(dev.DEFAULT.to_numpy(), X, family=sm.families.Binomial()).fit().params
    return {("(Intercept)" if k == "const" else k): float(v) for k, v in p.items()}


def score(df: pd.DataFrame, coefs: dict[str, float], woe: pd.DataFrame) -> pd.DataFrame:
    m = _woe_matrix(df, woe)
    eta = coefs["(Intercept)"] + sum(coefs[v] * m[v] for v in WOE_VARS.values())
    pd_ = expit(eta.to_numpy())
    factor = PDO / math.log(2)
    sc = np.round(BASE_SCORE - factor * math.log(BASE_ODDS) + factor * np.log((1 - pd_) / pd_))
    grade = np.array(["G", "F", "E", "D", "C", "B", "A"])[np.searchsorted(GRADE_CUTS, sc, side="right")]
    return pd.DataFrame({"ID": df.ID.to_numpy(), "pd": pd_, "score": sc, "grade": grade,
                         "decision": np.where(sc >= CUTOFF, "approve", "decline")})
