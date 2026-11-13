"""Data access for ModelProof (B4 contract). Everything reads the committed CSVs in data/processed."""
from typing import Literal

import pandas as pd

from modelproof import config

PROTECTED = ["SEX", "MARRIAGE", "AGE_BAND", "EDUCATION"]


def load_cr_pd_002(split: Literal["dev", "holdout", "edge"]) -> pd.DataFrame:
    return pd.read_csv(config.DATA_PROCESSED / f"cr_pd_002_{split}.csv")


def load_german() -> pd.DataFrame:
    return pd.read_csv(config.DATA_PROCESSED / "german_credit.csv")


def load_fraud() -> pd.DataFrame:
    return pd.read_csv(config.DATA_PROCESSED / "fraud_transactions.csv")


def age_band(age: pd.Series) -> pd.Series:
    return pd.cut(age, [-float("inf"), 24, 34, 44, 54, float("inf")], labels=["<25", "25-34", "35-44", "45-54", "55+"]).astype(str)
