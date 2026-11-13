"""Graph tests with every stage module faked: they check routing, gates, audit and threads only."""

import json
import sys
import types
from datetime import UTC, date, datetime

import pytest

from modelproof import audit, config, graph, inventory
from modelproof.schemas import InventoryRecord, MonitoringResult, ParityCertificate, ParityLevel


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        self.calls, self.parity, self.trigger = [], "PASS", None
        monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
        monkeypatch.setenv("MODELPROOF_RUN_ID", "t1")
        for name, attrs in self._modules().items():
            mod = types.ModuleType(name)
            mod.__dict__.update(attrs)
            monkeypatch.setitem(sys.modules, name, mod)

    def _modules(self):
        def stage(name, writes=None):
            def run(model_id, reviewer_comment=""):
                self.calls.append((name, model_id, reviewer_comment))
                if writes:
                    (config.artifact_dir(model_id) / writes[0]).write_text(json.dumps(writes[1]))

            return run

        def discover(model_id, reviewer_comment=""):
            self.calls.append(("discover", model_id, reviewer_comment))
            old = inventory.get(model_id)
            inventory.upsert(
                InventoryRecord(
                    model_id=model_id, name=f"{model_id} model", model_type="PD", platform_language="R",
                    materiality="H", complexity="M", risk_tier=1, documentation_status="current",
                    approvals=old.approvals if old else [],
                )
            )  # fmt: skip

        def redevelop(model_id, reviewer_comment=""):
            self.calls.append(("redevelop", model_id, reviewer_comment))
            lv = ParityLevel(
                level="L1",
                name="n",
                passed=self.parity == "PASS",
                metric="m",
                value=0.0,
                tolerance=1e-9,
            )
            return ParityCertificate(
                model_id=model_id, overall=self.parity, levels=[lv], hashes={}, versions={}, attempt=2,
                run_id="r", created_at=datetime.now(UTC),
            )  # fmt: skip

        def simulate(model_id, holdout, score_fn, months=6):
            self.calls.append(("monitor", model_id, months))
            return MonitoringResult(model_id=model_id, points=[], trigger_month=self.trigger)

        doc = {
            "claims": [{"status": "supported"}, {"status": "unsupported"}],
            "grounding_score": 0.5,
        }
        val = {
            "rating": "Fit with conditions",
            "results": {"tests": [{"rag": "green"}, {"rag": "red"}]},
        }
        return {
            "modelproof.agents.discover": {"run": discover},
            "modelproof.agents.document": {"run": stage("document", ("documentation.json", doc))},
            "modelproof.agents.redevelop": {"run": redevelop},
            "modelproof.agents.validate": {
                "run": stage("validate", ("validation_report.json", val))
            },
            "modelproof.tiering": {"next_due": lambda tier, last: date(2027, 1, 1)},
            "modelproof.data": {"load_cr_pd_002": lambda split: split},
            "modelproof.parity": {"score_fn": lambda path: lambda df: df},
            "modelproof.monitoring": {"simulate": simulate},
            "modelproof.tracking": {"log": lambda m: self.calls.append(("tracking", m))},
            "modelproof.report.render": {
                k: (lambda *a, k=k: self.calls.append(("render", k)))
                for k in ("inventory", "documentation", "parity", "validation")
            },
        }

    def stages(self):
        return [c[0] for c in self.calls if c[0] not in ("render", "tracking")]


@pytest.fixture
def h(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


def test_auto_run_target_model_loops_back_to_validate_once(h):
    h.trigger = 3
    r = graph.run("CR-PD-002", auto_approve=True)
    assert r["status"] == "completed" and r["inventory_status"] == "revalidation_required"
    assert h.stages() == [
        "discover",
        "document",
        "redevelop",
        "validate",
        "monitor",
        "validate",
        "monitor",
    ]
    rec = inventory.get("CR-PD-002")
    assert [a.gate for a in rec.approvals] == [
        "discovery", "documentation", "redevelopment", "validation", "validation",
    ]  # fmt: skip
    assert all(a.auto and a.reviewer == graph.AUTO_REVIEWER for a in rec.approvals)
    assert rec.last_validated is not None and rec.next_validation_due == date(2027, 1, 1)
    assert audit.verify_chain()
    events = [e["event"] for e in audit.read()]
    assert "monitoring.trigger" in events and events.count("gate.approve") == 5
    assert ("tracking", "CR-PD-002") in h.calls and ("render", "parity") in h.calls
    assert (config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").exists()


def test_auto_run_without_trigger_ends_monitored(h):
    r = graph.run("CR-PD-002", auto_approve=True)
    assert r["inventory_status"] == "monitored" and h.stages().count("validate") == 1


@pytest.mark.parametrize("model_id", ["CR-PD-001", "FR-TX-003", "PR-RB-004"])
def test_other_models_stop_after_documentation(h, model_id):
    r = graph.run(model_id, auto_approve=True)
    assert r["status"] == "completed" and r["inventory_status"] == "documented"
    assert h.stages() == ["discover", "document"]


def test_auto_never_promotes_failed_parity(h):
    h.parity = "FAIL"
    r = graph.run("CR-PD-002", auto_approve=True)
    assert r["status"] == "halted" and h.stages() == ["discover", "document", "redevelop"]
    last = inventory.get("CR-PD-002").approvals[-1]
    assert (last.gate, last.decision, last.auto) == ("redevelopment", "reject", True)
    assert inventory.get("CR-PD-002").status == "documented"


def test_human_gates_reject_with_comment_then_approve(h):
    r = graph.run("FR-TX-003")
    tid = r["thread_id"]
    assert r["status"] == "waiting" and r["gate"] == "discovery" and tid == "FR-TX-003:t1"
    assert h.stages() == ["discover"] and "tier 1" in r["summary"]
    assert graph.pending_gates() == [
        {"thread_id": tid, "model_id": "FR-TX-003", "gate": "discovery", "summary": r["summary"],
         "artifacts": ["inventory/inventory.json"]}
    ]  # fmt: skip

    r = graph.resume(tid, "approve", "looks right", "alice")
    assert r["gate"] == "documentation" and h.stages() == ["discover", "document"]
    r = graph.resume(tid, "reject", "section 3 is thin", "alice")
    assert r["status"] == "waiting" and r["gate"] == "documentation"
    assert (
        h.calls.count(("document", "FR-TX-003", "section 3 is thin")) == 1
    )  # comment reached the re-run
    r = graph.resume(tid, "approve", "", "alice")
    assert r["status"] == "completed" and graph.pending_gates() == []

    rec = inventory.get("FR-TX-003")
    assert [(a.gate, a.decision, a.reviewer, a.auto) for a in rec.approvals] == [
        ("discovery", "approve", "alice", False),
        ("documentation", "reject", "alice", False),
        ("documentation", "approve", "alice", False),
    ]
    assert rec.status == "documented" and audit.verify_chain()
    assert [e["actor"] for e in audit.read() if e["event"].startswith("gate.")] == ["alice"] * 3


def test_resume_validation(h):
    with pytest.raises(ValueError, match="approve or reject"):
        graph.resume("x:1", "maybe", "", "a")
    with pytest.raises(ValueError, match="no pending gate"):
        graph.resume("x:1", "approve", "", "a")
    with pytest.raises(ValueError, match="unknown model"):
        graph.run("NOPE")


def test_missing_renderer_does_not_stop_the_run(h, monkeypatch):
    monkeypatch.setitem(sys.modules, "modelproof.report.render", None)  # import raises
    assert graph.run("FR-TX-003", auto_approve=True)["status"] == "completed"
    assert any(e["event"] == "render.skipped" for e in audit.read())


def test_stage_timings_written_for_benchmark(h):
    graph.run("FR-TX-003", auto_approve=True)
    lines = [
        json.loads(x)
        for x in (config.ARTIFACTS / "runs" / "t1" / "timings.jsonl").read_text().splitlines()
    ]
    assert [(x["model_id"], x["stage"]) for x in lines] == [
        ("FR-TX-003", "discover"),
        ("FR-TX-003", "document"),
    ]
    assert all(x["seconds"] >= 0 and x["llm_mode"] for x in lines)
