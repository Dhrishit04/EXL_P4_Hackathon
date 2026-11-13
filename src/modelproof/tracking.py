"""Optional MLflow evidence tracking without a mandatory MLflow dependency."""

import importlib
import json
import math
import os
from pathlib import Path

from modelproof import config


def log(model_id) -> None:
    """Azure ML works by pointing MLFLOW_TRACKING_URI at the workspace and installing azureml-mlflow."""
    try:
        mlflow = importlib.import_module("mlflow")
    except ModuleNotFoundError as exc:
        if exc.name == "mlflow":
            return
        raise
    root = Path(config.ARTIFACTS)
    folder = (root / model_id).resolve()
    if folder.parent != root.resolve():
        raise ValueError("model_id must be a single directory name")
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if uri:
        mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("ModelProof")
    report_path = folder / "validation_report.json"
    results_path = folder / "validation_results.json"
    cert_path = folder / "parity_certificate.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    cert = json.loads(cert_path.read_text()) if cert_path.exists() else {}
    results = report.get("results", {})
    if not results and results_path.exists():
        results = json.loads(results_path.read_text())
    tier = "unknown"
    inventory_path = root / "inventory" / "inventory.json"
    if inventory_path.exists():
        records = json.loads(inventory_path.read_text())
        tier = next((str(row["risk_tier"]) for row in records if row["model_id"] == model_id), tier)
    tags = {"model_id": model_id, "tier": tier, "parity_status": cert.get("overall", "missing"),
            "rating": report.get("rating", "unavailable")}
    with mlflow.start_run(run_name=model_id):
        mlflow.set_tags(tags)
        for index, test in enumerate(results.get("tests", [])):
            value = test.get("value")
            if isinstance(value, (int, float)) and math.isfinite(value):
                mlflow.log_metric(f"check_{index}", value)
        if model_id == "CR-PD-002":
            coefficient_path = Path(config.LEGACY) / "CR-PD-002_r_card_default_pd" / "golden" / "coefficients.csv"
            if coefficient_path.exists():
                import pandas as pd

                for row in pd.read_csv(coefficient_path).itertuples(index=False):
                    mlflow.log_param(f"coef.{row.term}", row.estimate)
        for name in ["validation_results.json", "validation_report.json", "validation_report.html",
                     "parity_certificate.json", "parity_certificate.html", "monitoring.json"]:
            path = folder / name
            if path.exists():
                mlflow.log_artifact(str(path))
        if model_id == "CR-PD-002" and cert.get("overall") == "PASS":
            module_path = Path(config.REBUILT) / "cr_pd_002.py"
            if module_path.exists():
                from modelproof.parity import score_fn

                # Serialize the verified scorer so its coefficients and tables travel with the model.
                scorer = score_fn(module_path)

                class VerifiedModel(mlflow.pyfunc.PythonModel):
                    def predict(self, context, model_input, params=None):
                        return scorer(model_input)

                info = mlflow.pyfunc.log_model(artifact_path="model", python_model=VerifiedModel())
                version = mlflow.register_model(info.model_uri, "CR-PD-002-python")
                client = mlflow.MlflowClient()
                for key, value in tags.items():
                    client.set_model_version_tag("CR-PD-002-python", version.version, key, str(value))
