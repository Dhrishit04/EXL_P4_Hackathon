"""Compare two artifact trees (e.g. the live/record run and the replay run) and list every difference.

Ignored on purpose: wall-clock and run-identity fields (timestamps, run ids, date-derived due dates),
and files that are run logs by design (audit log, runs/, threads.json, checkpoints, metrics.json).
Usage: python scripts/replay_check.py ARTIFACTS_A ARTIFACTS_B   (exit 0 when identical)"""

import json
import re
import sys
from pathlib import Path

VOLATILE_KEYS = {
    "ts",
    "created_at",
    "generated_at",
    "run_id",
    "last_validated",
    "next_validation_due",
}
SKIP_PARTS = {"runs", "audit", "__pycache__", "inventory.lock"}
SKIP_NAMES = {"threads.json", "checkpoints.sqlite", "metrics.json", ".lock"}
ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")
TEXT = {".json", ".html", ".csv", ".txt", ".py", ".md", ".mmd"}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in VOLATILE_KEYS}
    return [_strip(v) for v in o] if isinstance(o, list) else o


def _canon(p: Path) -> bytes | str:
    if p.suffix == ".json":
        return json.dumps(_strip(json.loads(p.read_text(encoding="utf-8"))), sort_keys=True)
    if p.suffix in TEXT:
        return ISO_TS.sub("<ts>", p.read_text(encoding="utf-8"))
    return p.read_bytes()


def _files(root: Path) -> dict[str, Path]:
    return {
        str(p.relative_to(root)): p
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and not SKIP_PARTS & set(p.relative_to(root).parts)
        and p.name not in SKIP_NAMES
    }


def compare(a: Path, b: Path) -> list[str]:
    fa, fb = _files(a), _files(b)
    diffs = [f"only in {a}: {k}" for k in sorted(fa.keys() - fb.keys())]
    diffs += [f"only in {b}: {k}" for k in sorted(fb.keys() - fa.keys())]
    diffs += [
        f"differs: {k}" for k in sorted(fa.keys() & fb.keys()) if _canon(fa[k]) != _canon(fb[k])
    ]
    return diffs


if __name__ == "__main__":
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    diffs = compare(a, b)
    print("\n".join(diffs) if diffs else f"identical: {len(_files(a))} files compared")
    sys.exit(1 if diffs else 0)
