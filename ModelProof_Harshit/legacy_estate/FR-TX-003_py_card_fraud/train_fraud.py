from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

df = pd.read_csv(Path(__file__).resolve().parents[2] / "data/processed/fraud_transactions.csv")
df["night"] = (df.hour < 6).astype(int)
df["merchant_cat"] = df.merchant_cat.astype("category").cat.codes
X = df[["amount", "hour", "merchant_cat", "card_present", "country_mismatch", "txn_velocity_24h", "account_age_days"]]
Xtr, Xte, ytr, yte = train_test_split(X, df.is_fraud, test_size=0.3, stratify=df.is_fraud, random_state=42)
clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=42).fit(Xtr, ytr)
print("AUC", roc_auc_score(yte, clf.predict_proba(Xte)[:, 1]))
