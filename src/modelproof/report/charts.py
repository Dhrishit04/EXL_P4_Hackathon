"""Charts shared by HTML reports and the Streamlit workbench."""

import base64
from io import BytesIO

import numpy as np
from matplotlib.figure import Figure

NAVY = "#15324f"
ORANGE = "#dd7826"
RAG = {"green": "#24784b", "amber": "#b77900", "red": "#b93232"}


def _axes(title, xlabel, ylabel):
    fig = Figure(figsize=(7, 4), layout="constrained")
    ax = fig.subplots()
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.15)
    return fig, ax


def roc(fpr, tpr) -> Figure:
    fig, ax = _axes("ROC curve", "False positive rate", "True positive rate")
    ax.plot(fpr, tpr, color=NAVY)
    ax.plot([0, 1], [0, 1], "--", color="grey", linewidth=1)
    return fig


def ks(thresholds, good_cdf, bad_cdf) -> Figure:
    fig, ax = _axes("KS curves", "Risk probability", "Cumulative fraction")
    ax.plot(thresholds, good_cdf, label="Non-default", color=NAVY)
    ax.plot(thresholds, bad_cdf, label="Default", color=ORANGE)
    ax.legend()
    return fig


def calibration(predicted, observed) -> Figure:
    fig, ax = _axes("Calibration by decile", "Mean predicted default rate", "Observed default rate")
    ax.plot(predicted, observed, "o-", color=NAVY)
    ax.plot([0, 1], [0, 1], "--", color="grey", linewidth=1)
    return fig


def score_distribution(dev, holdout, bins=20) -> Figure:
    fig, ax = _axes("Score distribution", "Score", "Fraction of records")
    edges = np.histogram_bin_edges(np.concatenate([dev, holdout]), bins=bins)
    for values, label, color in [(dev, "Development", NAVY), (holdout, "Holdout", ORANGE)]:
        ax.hist(values, bins=edges, weights=np.ones(len(values)) / max(len(values), 1),
                histtype="step", label=label, color=color, linewidth=2)
    ax.legend()
    return fig


def score_histogram(edges, dev, holdout) -> Figure:
    """Render pre-aggregated counts without recreating individual records."""
    fig, ax = _axes("Score distribution", "Score", "Fraction of records")
    for counts, label, color in [(dev, "Development", NAVY), (holdout, "Holdout", ORANGE)]:
        values = np.asarray(counts, dtype=float)
        ax.stairs(values / max(values.sum(), 1), edges, label=label, color=color, linewidth=2)
    ax.legend()
    return fig


def psi_by_month(months, values, trigger_month=None, green=0.10, amber=0.25) -> Figure:
    fig, ax = _axes("Simulated drift — score PSI", "Simulated month", "Score PSI")
    ax.plot(months, values, "o-", color=NAVY)
    ax.axhline(green, color=RAG["amber"], linestyle="--", label=f"{green:g}")
    ax.axhline(amber, color=RAG["red"], linestyle="--", label=f"{amber:g}")
    if trigger_month is not None:
        ax.axvline(trigger_month, color=ORANGE, label="First trigger")
    ax.legend()
    return fig


def fairness(groups, values, metric="Approval rate") -> Figure:
    fig, ax = _axes(f"Fairness — {metric}", "Group", metric)
    ax.bar([str(group) for group in groups], values, color=NAVY)
    ax.set_ylim(0, 1)
    return fig


def rag_summary(tests) -> Figure:
    fig, ax = _axes("Validation check summary", "Status", "Number of checks")
    statuses = list(RAG)
    ax.bar(statuses, [sum((t.get("rag") if isinstance(t, dict) else t.rag) == status
                         for t in tests) for status in statuses], color=list(RAG.values()))
    ax.yaxis.get_major_locator().set_params(integer=True)
    return fig


def to_base64(fig) -> str:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
