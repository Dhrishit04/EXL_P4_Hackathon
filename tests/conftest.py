"""Shared test setup. Every test writes artifacts to its own tmp dir, never to the committed artifacts/."""

import pytest

from modelproof import config


@pytest.fixture(autouse=True)
def isolate_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
