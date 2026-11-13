import importlib.util
import json

from modelproof import config

SPEC = importlib.util.spec_from_file_location(
    "replay_check", config.ROOT / "scripts" / "replay_check.py"
)
rc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rc)


def tree(root, grounding=0.9, ts="2026-11-13T21:00:00+00:00", extra=None):
    (root / "M").mkdir(parents=True)
    (root / "M" / "documentation.json").write_text(
        json.dumps({"g": grounding, "created_at": ts, "run_id": ts})
    )
    (root / "M" / "report.html").write_text(f"<p>made {ts}</p>")
    (root / "runs" / "r").mkdir(parents=True)
    (root / "runs" / "r" / "llm_usage.jsonl").write_text(ts)
    (root / "audit").mkdir()
    (root / "audit" / "audit_log.jsonl").write_text(ts)
    for name in extra or []:
        (root / name).write_text("x")


def test_identical_apart_from_timestamps_and_run_logs(tmp_path):
    tree(tmp_path / "a")
    tree(tmp_path / "b", ts="2026-11-14T09:30:00+00:00")
    assert rc.compare(tmp_path / "a", tmp_path / "b") == []


def test_real_differences_are_reported(tmp_path):
    tree(tmp_path / "a")
    tree(tmp_path / "b", grounding=0.5, extra=["only_b.json"])
    assert rc.compare(tmp_path / "a", tmp_path / "b") == [
        f"only in {tmp_path / 'b'}: only_b.json",
        "differs: M/documentation.json",
    ]
