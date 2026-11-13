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
