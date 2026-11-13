"""Test-only module with the B5 interface that replays the R goldens (checks the harness plumbing, is NOT a rebuild).
PERTURB = True makes it mis-score rows whose util sits exactly on the 0 cut point (BILL_AMT1 == 0)."""
import numpy as np
import pandas as pd

from modelproof import config

G = config.model_dir("CR-PD-002") / "golden"
PERTURB = False
PAY = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "ID": df.ID, "util": df.BILL_AMT1 / df.LIMIT_BAL,
        "pay_ratio": (df.PAY_AMT1 / df.BILL_AMT1).where(df.BILL_AMT1 > 0),
        "n_delinq": (df[PAY] > 0).sum(axis=1), "worst_status": df[PAY].max(axis=1), "AGE": df.AGE, "LIMIT_BAL": df.LIMIT_BAL})


def apply_bins(features: pd.DataFrame) -> pd.DataFrame:
    return features


def woe_tables(dev_df: pd.DataFrame) -> pd.DataFrame:
    return pd.read_csv(G / "woe_tables.csv")


def fit(dev_df: pd.DataFrame) -> dict[str, float]:
    return dict(pd.read_csv(G / "coefficients.csv").values)


def score(df: pd.DataFrame, coefs: dict[str, float], woe: pd.DataFrame) -> pd.DataFrame:
    gold = pd.concat([pd.read_csv(G / f"scored_{s}.csv") for s in ("dev", "holdout", "edge")]).set_index("ID")
    out = gold.loc[df.ID].reset_index()
    if PERTURB:
        hit = np.asarray(df.BILL_AMT1 == 0)
        out.loc[hit, "pd"] += 1e-3
        out.loc[hit, "score"] -= 7
        out.loc[hit, "grade"] = "G"
        out.loc[hit, "decision"] = "decline"
    return out[["ID", "pd", "score", "grade", "decision"]]
