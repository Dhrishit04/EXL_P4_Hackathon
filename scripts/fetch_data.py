"""Download raw data to data/raw (gitignored) and write the processed CSVs committed to the repo.

Fraud generator (synthetic, seed 42): amount ~ lognormal(3.5, 1.2); hour ~ uniform 0-23; merchant_cat ~ categorical;
card_present ~ Bernoulli(0.65, 0.10 for online/electronics); country_mismatch ~ Bernoulli(0.03);
txn_velocity_24h ~ 1 + Poisson(1.5); account_age_days ~ 1 + Exponential(900).
is_fraud ~ Bernoulli(sigmoid(a + 0.35 ln amount + 1.2 night + 1.5 mismatch - 1.3 card_present + 0.25 velocity
+ 1.0 new_account + 0.8 risky_cat)), with the intercept `a` solved so the mean fraud rate is exactly 1%.
"""
import numpy as np
import pandas as pd
from modelproof.config import DATA_PROCESSED, DATA_RAW
from scipy.optimize import brentq
from scipy.special import expit
from sklearn.datasets import fetch_openml
from sklearn.model_selection import train_test_split

SEED = 42
TW_COLS = ["LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
           *[f"BILL_AMT{i}" for i in range(1, 7)], *[f"PAY_AMT{i}" for i in range(1, 7)]]


def taiwan() -> pd.DataFrame:
    try:
        from ucimlrepo import fetch_ucirepo
        d = fetch_ucirepo(id=350)
        X, y = d.data.features, d.data.targets.iloc[:, 0]
    except Exception:  # noqa: BLE001  any UCI failure -> OpenML 42477 via fairlearn
        from fairlearn.datasets import fetch_credit_card
        X, y = fetch_credit_card(as_frame=True, return_X_y=True)
    X = X.copy()
    assert X.shape[1] == 23, X.shape
    X.columns = TW_COLS  # positional: X1..X23 in the UCI documentation order
    df = pd.concat([X.reset_index(drop=True), y.reset_index(drop=True).astype(int).rename("DEFAULT")], axis=1)
    df.insert(0, "ID", np.arange(1, len(df) + 1))
    df = df.astype({c: "int64" for c in df.columns})
    assert len(df) == 30000 and df.SEX.isin([1, 2]).all() and df.AGE.between(21, 79).all()
    assert abs(df.DEFAULT.mean() - 0.2212) < 0.001, df.DEFAULT.mean()
    df.to_csv(DATA_RAW / "taiwan_raw.csv", index=False)
    return df


def german() -> pd.DataFrame:
    df = fetch_openml("credit-g", version=1, as_frame=True).frame
    df["bad"] = (df["class"] == "bad").astype(int)
    df = df.drop(columns="class")
    df.insert(0, "ID", np.arange(1, len(df) + 1))
    assert len(df) == 1000 and df.bad.mean() == 0.3
    df.to_csv(DATA_RAW / "german_raw.csv", index=False)
    return df


def fraud(n: int = 50_000) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    cats = np.array(["grocery", "fuel", "online_retail", "travel", "entertainment", "electronics", "other"])
    cat = rng.choice(cats, n, p=[0.28, 0.12, 0.2, 0.05, 0.1, 0.05, 0.2])
    risky = np.isin(cat, ["online_retail", "travel", "electronics"])
    df = pd.DataFrame({
        "ID": np.arange(1, n + 1),
        "amount": np.maximum(rng.lognormal(3.5, 1.2, n), 1).round(2),
        "hour": rng.integers(0, 24, n),
        "merchant_cat": cat,
        "card_present": (rng.random(n) < np.where(np.isin(cat, ["online_retail", "electronics"]), 0.10, 0.65)).astype(int),
        "country_mismatch": (rng.random(n) < 0.03).astype(int),
        "txn_velocity_24h": 1 + rng.poisson(1.5, n),
        "account_age_days": 1 + rng.exponential(900, n).astype(int),
    })
    z = (0.35 * np.log(df.amount) + 1.2 * (df.hour < 6) + 1.5 * df.country_mismatch - 1.3 * df.card_present
         + 0.25 * df.txn_velocity_24h + 1.0 * (df.account_age_days < 30) + 0.8 * risky).to_numpy()
    a = brentq(lambda a: expit(a + z).mean() - 0.01, -30, 5)
    df["is_fraud"] = (rng.random(n) < expit(a + z)).astype(int)
    return df


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    tw = taiwan()
    dev, ho = train_test_split(tw, test_size=0.3, stratify=tw.DEFAULT, random_state=SEED)
    dev.sort_values("ID").to_csv(DATA_PROCESSED / "cr_pd_002_dev.csv", index=False, lineterminator="\n")
    ho.sort_values("ID").to_csv(DATA_PROCESSED / "cr_pd_002_holdout.csv", index=False, lineterminator="\n")
    german().to_csv(DATA_PROCESSED / "german_credit.csv", index=False, lineterminator="\n")
    fraud().to_csv(DATA_PROCESSED / "fraud_transactions.csv", index=False, lineterminator="\n")


if __name__ == "__main__":
    main()
