"""Optional MLflow evidence tracking without a mandatory MLflow dependency."""

import importlib
import json
import math
import os
import re
from pathlib import Path

from modelproof import config


def _read_optional(path):
    return json.loads(path.read_text()) if path.exists() else {}


def _tags(root, model_id, report, certificate):
    inventory_path = root / "inventory" / "inventory.json"
    tier = "unknown"
    if inventory_path.exists():
        records = json.loads(inventory_path.read_text())
        tier = next((str(row["risk_tier"]) for row in records if row["model_id"] == model_id), tier)
    return {"model_id": model_id, "tier": tier,
            "parity_status": certificate.get("overall", "missing"),
            "rating": report.get("rating", "unavailable")}


def _log_metrics(mlflow, results):
    for index, test in enumerate(results.get("tests", [])):
        value = test.get("value")
        if isinstance(value, (int, float)) and math.isfinite(value):
            mlflow.log_metric(f"check_{index}", value)


def _safe_key(key):
    """MLflow keys allow letters, digits, _ - . space : / only; R names such as (Intercept) need cleaning."""
    return re.sub(r"[^\w\-. :/]", "", key)


def _log_coefficients(mlflow, model_id):
    if model_id != "CR-PD-002":
        return
    path = Path(config.LEGACY) / "CR-PD-002_r_card_default_pd" / "golden" / "coefficients.csv"
    if path.exists():
        import pandas as pd

        for row in pd.read_csv(path).itertuples(index=False):
            mlflow.log_param(_safe_key(f"coef.{row.term}"), row.estimate)


def _log_artifacts(mlflow, folder):
    for name in ["validation_results.json", "validation_report.json", "validation_report.html",
                 "parity_certificate.json", "parity_certificate.html", "monitoring.json"]:
        path = folder / name
        if path.exists():
            mlflow.log_artifact(str(path))


def _register_verified_model(mlflow, model_id, certificate, tags):
    if model_id != "CR-PD-002" or certificate.get("overall") != "PASS":
        return
    module_path = Path(config.REBUILT) / "cr_pd_002.py"
    if not module_path.exists():
        return
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
    report = _read_optional(folder / "validation_report.json")
    certificate = _read_optional(folder / "parity_certificate.json")
    results = report.get("results") or _read_optional(folder / "validation_results.json")
    tags = _tags(root, model_id, report, certificate)
    with mlflow.start_run(run_name=model_id):
        mlflow.set_tags(tags)
        _log_metrics(mlflow, results)
        _log_coefficients(mlflow, model_id)
        _log_artifacts(mlflow, folder)
        _register_verified_model(mlflow, model_id, certificate, tags)
