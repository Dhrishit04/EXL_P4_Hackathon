"""Group assessment using approval as the favourable outcome."""
import numpy as np
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_ratio,
    equalized_odds_difference,
)

from modelproof.metrics import auc


def report(df, y: str, approved: str, score: str, sensitive: list[str]) -> dict:
    if df.empty:
        raise ValueError("Fairness assessment requires observations")
    if not df[y].isin([0, 1]).all() or not df[approved].isin([0, 1, True, False]).all():
        raise ValueError("Outcome and approval columns must be binary")
    # DEFAULT=1 is adverse. Approval TPR therefore uses repayment (1-DEFAULT).
    favourable = 1 - df[y].to_numpy(dtype=int)
    decisions = df[approved].to_numpy(dtype=int)
    risk = df[score].to_numpy(dtype=float)
    groups, assessments, ratios, differences = [], {}, [], []
    for column in sensitive:
        labels = df[column].astype("string").fillna("<missing>").to_numpy(dtype=str)
        frame = MetricFrame(metrics={
            "approval_rate": lambda truth, pred: float(np.mean(pred)),
            "tpr": lambda truth, pred: float(np.mean(pred[truth == 1])) if np.any(truth == 1) else np.nan,
            "fpr": lambda truth, pred: float(np.mean(pred[truth == 0])) if np.any(truth == 0) else np.nan,
        }, y_true=favourable, y_pred=decisions, sensitive_features=labels)
        records = []
        for label, row in frame.by_group.iterrows():
            mask = labels == label
            record = {"sensitive": column, "group": str(label), "n": int(mask.sum()),
                      "n_repaid": int(favourable[mask].sum()), "n_default": int((1-favourable[mask]).sum()),
                      **{key: float(value) if np.isfinite(value) else None for key, value in row.items()}}
            group_auc = auc(df[y].to_numpy()[mask], risk[mask])
            record["auc"] = float(group_auc) if np.isfinite(group_auc) else None
            record["uncertain"] = bool(mask.sum() < 30 or record["n_repaid"] == 0 or record["n_default"] == 0)
            records.append(record)
        rates = frame.by_group.approval_rate
        ratio = float(demographic_parity_ratio(favourable, decisions, sensitive_features=labels)) if rates.max() > 0 else None
        complete = all(record["tpr"] is not None and record["fpr"] is not None for record in records)
        difference = float(equalized_odds_difference(favourable, decisions, sensitive_features=labels)) if complete else None
        assessments[column] = {"groups": records, "demographic_parity_ratio": ratio,
                               "equalized_odds_difference": difference}
        groups.extend(records)
        if ratio is not None:
            ratios.append(ratio)
        if difference is not None:
            differences.append(difference)
    worst_ratio = min(ratios) if ratios else None
    return {"by_sensitive": assessments, "by_group": groups, "groups": groups,
            "worst_dp_ratio": worst_ratio, "worst_eod": max(differences) if differences else None,
            "four_fifths_flag": worst_ratio < 0.8 if worst_ratio is not None else None,
            "outcome_definition": "Approval is positive; TPR is approval among repayers, FPR is approval among defaulters; AUC uses default probability."}
