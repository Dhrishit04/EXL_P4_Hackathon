"""Deterministic validation metrics. Undefined statistics return NaN."""
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy import stats

MISSING_LABEL = "<missing>"


def _inputs(y, p):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or not len(y):
        raise ValueError("y and p must be nonempty one-dimensional arrays of equal length")
    if not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("Inputs must be finite")
    if not np.isin(y, [0, 1]).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Labels must be binary and probabilities in [0, 1]")
    return y, p


def auc(y, p) -> float:
    y, p = _inputs(y, p)
    positives = y.sum()
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = stats.rankdata(p)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def gini(y, p) -> float:
    return 2 * auc(y, p) - 1


def ks(y, p) -> float:
    y, p = _inputs(y, p)
    if len(np.unique(y)) != 2:
        return float("nan")
    return float(stats.ks_2samp(p[y == 0], p[y == 1]).statistic)


def brier(y, p) -> float:
    y, p = _inputs(y, p)
    return float(np.mean((y - p) ** 2))


def bootstrap_ci(fn: Callable, y, p, n=500, seed=42) -> tuple[float, float]:
    y, p = _inputs(y, p)
    if n < 1:
        raise ValueError("n must be positive")
    indices = np.random.default_rng(seed).integers(0, len(y), size=(n, len(y)))
    values = np.asarray([fn(y[index], p[index]) for index in indices])
    values = values[np.isfinite(values)]
    if not len(values):
        return float("nan"), float("nan")
    return tuple(float(v) for v in np.percentile(values, [2.5, 97.5]))


def calibration_table(y, p, bins=10) -> pd.DataFrame:
    y, p = _inputs(y, p)
    if bins < 1:
        raise ValueError("bins must be positive")
    frame = pd.DataFrame({"y": y, "p": p})
    # Preserve tied predictions in the same bin.
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    frame["bin"] = pd.cut(p, edges, include_lowest=True) if len(edges) > 1 else "all"
    result = frame.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean")
    ).reset_index()
    result["bin"] = result["bin"].astype(str)
    return result


def hosmer_lemeshow(y, p, groups=10) -> tuple[float, float]:
    table = calibration_table(y, p, groups)
    expected = table.n * table.mean_predicted
    observed = table.n * table.observed_rate
    denominator = table.n * table.mean_predicted * (1 - table.mean_predicted)
    terms = np.divide((observed - expected) ** 2, denominator,
                      out=np.zeros(len(table)), where=denominator.to_numpy() > 0)
    if ((denominator == 0) & (observed != expected)).any():
        return float("inf"), 0.0
    statistic = float(terms.sum())
    # The effective number of groups can shrink when predictions tie.
    dof = len(table) - 2
    return statistic, float(stats.chi2.sf(statistic, dof)) if dof > 0 else float("nan")


def jeffreys_by_grade(df, grade="grade", pd_col="pd", y="DEFAULT", alpha=0.05) -> pd.DataFrame:
    _inputs(df[y], df[pd_col])
    if not np.isfinite(alpha) or alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be between zero and one")
    table = df.groupby(grade, observed=True, dropna=False).agg(
        N=(y, "size"), D=(y, "sum"), mean_pd=(pd_col, "mean")
    ).reset_index()
    table["p"] = stats.beta.cdf(table.mean_pd, table.D + 0.5, table.N - table.D + 0.5)
    table["fail"] = table.p < alpha
    return table


def psi(expected, actual, bins=10) -> float:
    expected, actual = pd.Series(expected), pd.Series(actual)
    if not len(expected) or not len(actual):
        raise ValueError("PSI populations must be nonempty")
    if bins < 1:
        raise ValueError("bins must be positive")
    if pd.api.types.is_numeric_dtype(expected) and pd.api.types.is_numeric_dtype(actual):
        ref = expected.replace([np.inf, -np.inf], np.nan)
        cur = actual.replace([np.inf, -np.inf], np.nan)
        clean = ref.dropna().to_numpy()
        internal = np.unique(np.quantile(clean, np.linspace(0, 1, bins + 1))) if len(clean) else np.array([])
        if len(internal) == 1:
            value = internal[0]
            # Give changes from a constant reference their own population bucket.
            e = np.array([(ref < value).sum(), (ref == value).sum(), (ref > value).sum(), ref.isna().sum()])
            a = np.array([(cur < value).sum(), (cur == value).sum(), (cur > value).sum(), cur.isna().sum()])
        else:
            edges = np.r_[-np.inf, internal[1:-1], np.inf]
            e = np.r_[np.histogram(ref.dropna(), edges)[0], ref.isna().sum()]
            a = np.r_[np.histogram(cur.dropna(), edges)[0], cur.isna().sum()]
    else:
        ref, cur = expected.astype("string").fillna(MISSING_LABEL), actual.astype("string").fillna(MISSING_LABEL)
        categories = pd.Index(ref.unique()).union(pd.Index(cur.unique()))
        e = ref.value_counts().reindex(categories, fill_value=0).to_numpy()
        a = cur.value_counts().reindex(categories, fill_value=0).to_numpy()
    e = np.maximum(e / len(expected), 1e-6)
    a = np.maximum(a / len(actual), 1e-6)
    return float(np.sum((a - e) * np.log(a / e)))


def csi(ref: pd.DataFrame, cur: pd.DataFrame, cols) -> dict[str, float]:
    return {str(column): psi(ref[column], cur[column]) for column in cols}


def woe_iv(binned: pd.Series, y: pd.Series) -> tuple[pd.DataFrame, float]:
    labels = pd.Series(binned).astype("string").fillna(MISSING_LABEL).to_numpy()
    target = np.asarray(y)
    if len(labels) != len(target) or not len(labels) or not np.isin(target, [0, 1]).all():
        raise ValueError("Bins and binary labels must have the same nonzero length")
    table = pd.DataFrame({"bin": labels, "y": target}).groupby("bin").agg(n=("y", "size"), n_bad=("y", "sum"))
    table["n_good"] = table.n - table.n_bad
    # Half-event smoothing avoids infinite WoE for empty event cells.
    bad = (table.n_bad + 0.5) / (table.n_bad.sum() + 0.5 * len(table))
    good = (table.n_good + 0.5) / (table.n_good.sum() + 0.5 * len(table))
    table["woe"] = np.log(good / bad)
    table["iv"] = (good - bad) * table.woe
    return table.reset_index(), float(table.iv.sum())


def vif(df: pd.DataFrame) -> dict[str, float]:
    values = df.to_numpy(dtype=float)
    if len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("VIF requires at least two finite rows")
    result = {}
    for index, column in enumerate(df.columns):
        target = values[:, index]
        total = np.sum((target - target.mean()) ** 2)
        predictors = np.column_stack([np.ones(len(values)), np.delete(values, index, axis=1)])
        residual = target - predictors @ np.linalg.lstsq(predictors, target, rcond=None)[0]
        fraction = np.sum(residual ** 2) / total if total > 0 else 0
        result[str(column)] = float(1 / fraction) if fraction > 1e-12 else float("inf")
    return result


def hhi(labels: pd.Series) -> float:
    shares = pd.Series(labels).value_counts(normalize=True, dropna=False)
    return float((shares ** 2).sum()) if len(shares) else float("nan")
