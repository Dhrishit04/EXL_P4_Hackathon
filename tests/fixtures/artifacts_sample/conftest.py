from __future__ import annotations

from pathlib import Path


def pytest_ignore_collect(collection_path: Path, config: object) -> bool | None:
    if collection_path.name == "test_cr_pd_002.py":
        return True
    return None
