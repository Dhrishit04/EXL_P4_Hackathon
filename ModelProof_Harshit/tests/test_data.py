import pandas as pd

from modelproof import data

COLS = ["ID", "LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
        *[f"BILL_AMT{i}" for i in range(1, 7)], *[f"PAY_AMT{i}" for i in range(1, 7)], "DEFAULT"]


def test_taiwan_split_is_stratified_70_30_and_disjoint():
    dev, ho = data.load_cr_pd_002("dev"), data.load_cr_pd_002("holdout")
    assert list(dev.columns) == COLS and list(ho.columns) == COLS
    assert (len(dev), len(ho)) == (21000, 9000)
    assert not set(dev.ID) & set(ho.ID)
    assert abs(dev.DEFAULT.mean() - 0.2212) < 0.002 and abs(ho.DEFAULT.mean() - 0.2212) < 0.002
    assert dev.SEX.isin([1, 2]).all() and dev.AGE.between(21, 79).all()


def test_german_and_fraud():
    g, f = data.load_german(), data.load_fraud()
    assert len(g) == 1000 and {"ID", "bad", "personal_status"} <= set(g.columns) and g.bad.mean() == 0.3
    assert len(f) == 50000 and 0.005 < f.is_fraud.mean() < 0.02
    assert list(f.columns) == ["ID", "amount", "hour", "merchant_cat", "card_present", "country_mismatch",
                               "txn_velocity_24h", "account_age_days", "is_fraud"]


def test_age_band_and_protected():
    out = data.age_band(pd.Series([21, 24, 25, 34, 35, 44, 45, 54, 55, 79]))
    assert out.tolist() == ["<25", "<25", "25-34", "25-34", "35-44", "35-44", "45-54", "45-54", "55+", "55+"]
    assert data.PROTECTED == ["SEX", "MARRIAGE", "AGE_BAND", "EDUCATION"]
