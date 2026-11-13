from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from streamlit.errors import StreamlitSecretNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "artifacts_sample"


def _secret_artifacts() -> str | None:
    try:
        return st.secrets.get("MODELPROOF_ARTIFACTS")
    except StreamlitSecretNotFoundError:
        return None


def resolve_artifacts(
    secret_value: str | None = None,
    env_value: str | None = None,
    root: Path = ROOT,
) -> tuple[Path, bool]:
    configured = secret_value or env_value or "artifacts"
    requested = Path(configured).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    if (requested / "inventory" / "inventory.json").is_file():
        fixture_dir = root / "tests" / "fixtures" / "artifacts_sample"
        return requested, requested.resolve() == fixture_dir.resolve()
    return root / "tests" / "fixtures" / "artifacts_sample", True


ARTIFACTS, IS_FIXTURE = resolve_artifacts(_secret_artifacts(), os.environ.get("MODELPROOF_ARTIFACTS"))

try:
    from modelproof import schemas as _schemas
except ImportError:
    _schemas = None


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _parse(data: Any, schema_name: str | None = None) -> Any:
    if schema_name is None:
        return data
    if _schemas is None:
        raise RuntimeError(f"modelproof.schemas is unavailable; cannot validate {schema_name}")
    schema = getattr(_schemas, schema_name, None)
    if schema is None:
        raise RuntimeError(f"modelproof.schemas has no {schema_name} model")
    if isinstance(data, list):
        return [_model_dump(schema.model_validate(item)) for item in data]
    return _model_dump(schema.model_validate(data))


def _schema_for(relative_path: str, explicit_name: str | None) -> str | None:
    if explicit_name is not None:
        return explicit_name
    name = Path(relative_path).name
    return {
        "facts.json": "Facts",
        "documentation.json": "Documentation",
        "certificate.json": "ParityCertificate",
        "parity_certificate.json": "ParityCertificate",
        "validation_results.json": "ValidationResults",
        "validation_report.json": "ValidationReport",
        "monitoring.json": "MonitoringResult",
    }.get(name)


@lru_cache(maxsize=128)
def _read_json(path_string: str) -> Any:
    path = Path(path_string)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def read_json(relative_path: str, schema_name: str | None = None) -> Any:
    path = ARTIFACTS / relative_path
    try:
        data = _read_json(str(path))
    except (OSError, json.JSONDecodeError) as error:
        st.warning(f"Invalid artifact file {relative_path}: {error}")
        return None
    if data is None:
        st.warning(f"Missing artifact file: {relative_path}")
        return None
    try:
        return _parse(data, _schema_for(relative_path, schema_name))
    except (ValidationError, RuntimeError, ValueError) as error:
        st.warning(f"Invalid artifact file {relative_path}: {error}")
        return None


def load_inventory() -> list[dict[str, Any]]:
    data = read_json("inventory/inventory.json", "InventoryRecord")
    if not isinstance(data, list):
        return []
    return data


def model_ids() -> list[str]:
    records = load_inventory()
    discovered = [str(record["model_id"]) for record in records if record.get("model_id")]
    if discovered:
        return discovered
    return sorted(
        path.name
        for path in ARTIFACTS.iterdir()
        if path.is_dir() and (path / "validation_results.json").exists()
    ) if ARTIFACTS.is_dir() else []


def model_record(model_id: str) -> dict[str, Any] | None:
    return next((row for row in load_inventory() if row.get("model_id") == model_id), None)


def model_artifact(model_id: str, filename: str, schema_name: str | None = None) -> Any:
    return read_json(f"{model_id}/{filename}", schema_name)


def dataframe(rows: Any) -> pd.DataFrame:
    return pd.DataFrame(rows if isinstance(rows, list) else [])


def available_html(model_id: str, filename: str) -> str | None:
    path = ARTIFACTS / model_id / filename
    return str(path) if path.is_file() else None
