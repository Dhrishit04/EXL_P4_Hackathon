"""Append-only, hash-chained audit log: artifacts/audit/audit_log.jsonl.
entry = {ts, actor, event, model_id, payload, prev_hash, hash}
hash  = sha256(prev_hash + canonical_json(entry_without_hash))"""

import hashlib
import json
from datetime import UTC, datetime

from modelproof import config

try:
    import fcntl
except ImportError:  # non-POSIX: no inter-process lock
    fcntl = None

GENESIS = "0" * 64


def _default(o):
    return o.model_dump(mode="json") if hasattr(o, "model_dump") else str(o)


def _canon(entry: dict) -> str:
    return json.dumps(
        entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    )


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((entry["prev_hash"] + _canon(body)).encode()).hexdigest()


def _path():
    return config.ARTIFACTS / "audit" / "audit_log.jsonl"


def append(event: str, payload: dict, model_id: str | None = None, actor: str = "system") -> str:
    """Append one entry and return its hash."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        lines = f.read().splitlines()
        prev = json.loads(lines[-1])["hash"] if lines else GENESIS
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "actor": actor,
            "event": event,
            "model_id": model_id,
            "payload": json.loads(
                _canon(payload)
            ),  # normalise so the stored form is what is hashed
            "prev_hash": prev,
        }
        entry["hash"] = _hash(entry)
        f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return entry["hash"]


def read() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_chain() -> bool:
    """True if every entry links to its predecessor and its hash recomputes."""
    try:
        entries = read()
    except json.JSONDecodeError:
        return False
    prev = GENESIS
    for e in entries:
        if e.get("prev_hash") != prev or e.get("hash") != _hash(e):
            return False
        prev = e["hash"]
    return True
