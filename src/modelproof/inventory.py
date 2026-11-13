"""Model inventory store: artifacts/inventory/inventory.json (+ .csv). Upsert by model_id."""

import csv
import json
from contextlib import contextmanager

from modelproof import config
from modelproof.schemas import InventoryRecord

try:
    import fcntl
except ImportError:  # non-POSIX: no inter-process lock
    fcntl = None

CSV_COLUMNS = [
    "model_id", "name", "version", "model_type", "platform_language", "risk_tier", "materiality",
    "complexity", "documentation_status", "status", "n_drifts", "n_security_flags",
    "last_validated", "next_validation_due", "upstream_models", "downstream_models", "purpose",
]  # fmt: skip


def _dir():
    d = config.ARTIFACTS / "inventory"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _lock():
    with open(_dir() / ".lock", "w") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        yield


def load() -> list[InventoryRecord]:
    p = _dir() / "inventory.json"
    if not p.exists():
        return []
    return [InventoryRecord.model_validate(r) for r in json.loads(p.read_text())]


def get(model_id: str) -> InventoryRecord | None:
    return next((r for r in load() if r.model_id == model_id), None)


def _row(r: InventoryRecord) -> dict:
    d = r.model_dump(mode="json")
    d.update(
        n_drifts=len(r.doc_code_drifts),
        n_security_flags=len(r.security_flags),
        upstream_models="; ".join(r.upstream_models),
        downstream_models="; ".join(r.downstream_models),
    )
    return {k: d[k] for k in CSV_COLUMNS}


def upsert(rec: InventoryRecord) -> None:
    with _lock():
        recs = {r.model_id: r for r in load()}
        recs[rec.model_id] = rec
        order = list(config.MODELS)
        rows = sorted(
            recs.values(),
            key=lambda r: (order.index(r.model_id) if r.model_id in order else 99, r.model_id),
        )
        d = _dir()
        (d / "inventory.json").write_text(
            json.dumps([r.model_dump(mode="json") for r in rows], indent=2) + "\n"
        )
        with open(d / "inventory.csv", "w", newline="") as f:
            w = csv.DictWriter(f, CSV_COLUMNS)
            w.writeheader()
            w.writerows(_row(r) for r in rows)


def update(model_id: str, **changes) -> InventoryRecord:
    """Merge field changes into an existing record (validated) and persist it."""
    rec = get(model_id)
    if rec is None:
        raise KeyError(f"{model_id} is not in the inventory yet (run discover first)")
    new = InventoryRecord.model_validate({**rec.model_dump(), **changes})
    upsert(new)
    return new
