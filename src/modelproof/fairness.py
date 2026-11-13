"""Group assessment using approval as the favourable outcome."""
import numpy as np
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_ratio,
    equalized_odds_difference,
)

from modelproof.metrics import auc


def _conditional_rate(truth, predicted, outcome):
    selected = predicted[truth == outcome]
    return float(np.mean(selected)) if len(selected) else np.nan


def _finite_or_none(value):
    return float(value) if np.isfinite(value) else None


def _group_records(frame, labels, column, favourable, target, risk):
    records = []
    for label, row in frame.by_group.iterrows():
        mask = labels == label
        repaid = int(favourable[mask].sum())
        defaults = int((1 - favourable[mask]).sum())
        records.append({
            "sensitive": column, "group": str(label), "n": int(mask.sum()),
            "n_repaid": repaid, "n_default": defaults,
            **{key: _finite_or_none(value) for key, value in row.items()},
            "auc": _finite_or_none(auc(target[mask], risk[mask])),
            "uncertain": bool(mask.sum() < 30 or repaid == 0 or defaults == 0),
        })
    return records


def _assess_column(df, column, favourable, decisions, target, risk):
    labels = df[column].astype("string").fillna("<missing>").to_numpy(dtype=str)
    frame = MetricFrame(metrics={
        "approval_rate": lambda truth, pred: float(np.mean(pred)),
        "tpr": lambda truth, pred: _conditional_rate(truth, pred, 1),
        "fpr": lambda truth, pred: _conditional_rate(truth, pred, 0),
    }, y_true=favourable, y_pred=decisions, sensitive_features=labels)
    records = _group_records(frame, labels, column, favourable, target, risk)
    ratio = None
    if frame.by_group.approval_rate.max() > 0:
        ratio = float(demographic_parity_ratio(favourable, decisions, sensitive_features=labels))
    difference = None
    complete = all(record["tpr"] is not None and record["fpr"] is not None for record in records)
    if complete:
        difference = float(equalized_odds_difference(favourable, decisions, sensitive_features=labels))
    return {"groups": records, "demographic_parity_ratio": ratio,
            "equalized_odds_difference": difference}


def report(df, y: str, approved: str, score: str, sensitive: list[str]) -> dict:
    if df.empty:
        raise ValueError("Fairness assessment requires observations")
    if not df[y].isin([0, 1]).all() or not df[approved].isin([0, 1, True, False]).all():
        raise ValueError("Outcome and approval columns must be binary")
    # DEFAULT=1 is adverse. Approval TPR therefore uses repayment (1-DEFAULT).
    target = df[y].to_numpy(dtype=int)
    favourable = 1 - target
    decisions = df[approved].to_numpy(dtype=int)
    risk = df[score].to_numpy(dtype=float)
    assessments = {column: _assess_column(df, column, favourable, decisions, target, risk)
                   for column in sensitive}
    return _summarize(assessments)


def _summarize(assessments):
    groups = [record for result in assessments.values() for record in result["groups"]]
    ratios = [result["demographic_parity_ratio"] for result in assessments.values()
              if result["demographic_parity_ratio"] is not None]
    differences = [result["equalized_odds_difference"] for result in assessments.values()
                   if result["equalized_odds_difference"] is not None]
    worst_ratio = min(ratios) if ratios else None
    return {"by_sensitive": assessments, "by_group": groups, "groups": groups,
            "worst_dp_ratio": worst_ratio, "worst_eod": max(differences) if differences else None,
            "four_fifths_flag": worst_ratio < 0.8 if worst_ratio is not None else None,
            "outcome_definition": "Approval is positive; TPR is approval among repayers, FPR is approval among defaulters; AUC uses default probability."}
