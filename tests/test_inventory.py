import csv

import pytest

from modelproof import config, inventory
from modelproof.schemas import InventoryRecord


@pytest.fixture(autouse=True)
def tmp_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    return tmp_path


def rec(model_id, **kw):
    base = dict(model_id=model_id, name=model_id, model_type="PD", platform_language="R",
                materiality="H", complexity="M", risk_tier=1, documentation_status="current")  # fmt: skip
    return InventoryRecord(**{**base, **kw})


def test_upsert_orders_by_registry_and_replaces(tmp_artifacts):
    assert inventory.load() == [] and inventory.get("CR-PD-002") is None
    inventory.upsert(rec("PR-RB-004"))
    inventory.upsert(rec("CR-PD-001"))
    inventory.upsert(rec("CR-PD-001", name="renamed", upstream_models=["X"]))
    assert [r.model_id for r in inventory.load()] == ["CR-PD-001", "PR-RB-004"]
    assert inventory.get("CR-PD-001").name == "renamed"
    rows = list(csv.DictReader(open(tmp_artifacts / "inventory" / "inventory.csv")))
    assert rows[0]["upstream_models"] == "X" and rows[0]["n_drifts"] == "0"


def test_update_validates_and_requires_record():
    with pytest.raises(KeyError):
        inventory.update("CR-PD-002", status="validated")
    inventory.upsert(rec("CR-PD-002"))
    assert inventory.update("CR-PD-002", status="validated").status == "validated"
    assert inventory.get("CR-PD-002").status == "validated"
    with pytest.raises(ValueError):
        inventory.update("CR-PD-002", status="not-a-status")
