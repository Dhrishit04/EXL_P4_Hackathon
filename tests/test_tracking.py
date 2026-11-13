import importlib

from modelproof import tracking


def test_missing_mlflow_is_silent(monkeypatch):
    original = importlib.import_module

    def missing(name):
        if name == "mlflow":
            raise ModuleNotFoundError("No module named mlflow", name="mlflow")
        return original(name)

    monkeypatch.setattr(importlib, "import_module", missing)
    assert tracking.log("CR-PD-002") is None


def test_logs_finite_metrics_and_artifacts_without_registering(monkeypatch, tmp_path):
    import json
    from contextlib import nullcontext
    from unittest.mock import MagicMock

    from modelproof import config

    folder = config.artifact_dir("fixture-model")
    results = {"tests": [{"value": 0.75}, {"value": None}, {"value": float("nan")}]}
    (folder / "validation_results.json").write_text(json.dumps(results))
    mlflow = MagicMock()
    mlflow.start_run.return_value = nullcontext()
    original = importlib.import_module
    monkeypatch.setattr(importlib, "import_module", lambda name: mlflow if name == "mlflow" else original(name))

    tracking.log("fixture-model")

    mlflow.log_metric.assert_called_once_with("check_0", 0.75)
    mlflow.log_artifact.assert_called_once_with(str(folder / "validation_results.json"))
    mlflow.register_model.assert_not_called()
    tags = mlflow.set_tags.call_args.args[0]
    assert tags["model_id"] == "fixture-model"
    assert tags["parity_status"] == "missing"
