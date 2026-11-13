"""Simulated drift only: observed outcome labels remain fixed after stress."""

import matplotlib
import numpy as np
import pandas as pd
from modelproof.schemas import MonitoringPoint, MonitoringResult

from modelproof import audit, config, metrics
from modelproof.validation import scored_rows


def simulate(model_id, holdout: pd.DataFrame, score_fn, months: int = 6) -> MonitoringResult:
    """Apply documented synthetic input stress; labels stay as originally observed."""
    if not isinstance(months, int) or not 1 <= months <= 6:
        raise ValueError("The documented simulation supports one to six months")
    policy = config.load_policy()
    reference = scored_rows(holdout, score_fn)
    baseline_gini = metrics.gini(reference.DEFAULT, reference["pd"])
    points = []
    stress = {4: (1.15, 0.10), 5: (1.30, 0.20), 6: (1.50, 0.30)}
    for month in range(1, months + 1):
        rng = np.random.default_rng(42 + month)
        # A bootstrap contains repeated original IDs. Assign simulation IDs before scoring.
        current = holdout.iloc[rng.integers(0, len(holdout), size=3000)].copy().reset_index(drop=True)
        current["ID"] = np.arange(len(current))
        if month in stress:
            multiplier, share = stress[month]
            current["BILL_AMT1"] = current.BILL_AMT1 * multiplier
            selected = rng.choice(len(current), size=round(share * len(current)), replace=False)
            current.loc[selected, "PAY_0"] = current.loc[selected, "PAY_0"] + 1
        scored = scored_rows(current, score_fn)
        gini = metrics.gini(scored.DEFAULT, scored["pd"])
        score_psi = metrics.psi(reference.score, scored.score)
        failures = int(metrics.jeffreys_by_grade(scored, alpha=policy["jeffreys"]["alpha"])["fail"].sum())
        triggers = policy["monitoring_triggers"]
        breaches = []
        if score_psi >= triggers["score_psi"]:
            breaches.append("score_psi")
        if baseline_gini <= 0:
            breaches.append("reference_gini_nonpositive")
        elif (baseline_gini - gini) / baseline_gini >= triggers["gini_drop_rel"]:
            breaches.append("gini_drop_rel")
        if failures >= triggers["jeffreys_failures"]:
            breaches.append("jeffreys_failures")
        points.append(MonitoringPoint(month=month, score_psi=score_psi,
                      csi=metrics.csi(holdout, current, ["BILL_AMT1", "PAY_0"]), gini=gini,
                      observed_dr=float(scored.DEFAULT.mean()), expected_dr=float(scored["pd"].mean()),
                      jeffreys_failures=failures, breaches=breaches))
    result = MonitoringResult(model_id=model_id, points=points,
                              trigger_month=next((p.month for p in points if p.breaches), None), simulated=True)
    out = config.artifact_dir(model_id)
    (out / "monitoring.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot([p.month for p in points], [p.score_psi for p in points], color="#16324f", marker="o")
    for label, color in (("green", "#d28b00"), ("amber", "#c0392b")):
        value = policy["psi"][label]
        ax.axhline(value, color=color, linestyle="--", label=f"Policy PSI {value}")
    if result.trigger_month is not None:
        ax.axvline(result.trigger_month, color="#ee8131", linestyle=":", label="First monitoring trigger")
    ax.set(xlabel="Simulated month", ylabel="Score PSI", title="Simulated drift — observed labels retained")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "monitoring.png", dpi=150)
    plt.close(fig)
    audit.append("monitoring_simulated", {"months": months, "trigger_month": result.trigger_month,
                 "limitation": "Simulated input drift; labels remain as observed."}, model_id=model_id)
    return result
