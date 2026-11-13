"""LangGraph orchestration with human gates (governance by construction).

CR-PD-002 : discover > gate > document > gate > redevelop > gate > validate > gate > monitor
            (a monitoring trigger routes back to validate once, then END)
others    : discover > gate > document > gate > END

A gate node only calls `interrupt(...)` and then records the Approval. Nothing with side effects
runs before the interrupt because the node re-executes from the top when the run is resumed.
Stage modules are imported lazily so this module imports even before every work package has landed."""

import importlib
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from modelproof import audit, config, inventory, llm
from modelproof.schemas import Approval

AUTO_REVIEWER = "auto (demo flag)"
STATUS_AFTER = {
    "documentation": "documented",
    "redevelopment": "redeveloped",
    "validation": "validated",
}
ARTIFACT_FILES = {
    "discovery": ["inventory/inventory.json", "{m}/facts.json"],
    "documentation": ["{m}/documentation.json", "{m}/documentation.html"],
    "redevelopment": ["{m}/parity_certificate.json", "{m}/parity_certificate.html"],
    "validation": [
        "{m}/validation_report.json",
        "{m}/validation_report.html",
        "{m}/monitoring.png",
    ],
}


class State(TypedDict, total=False):
    model_id: str
    auto: bool
    feedback: dict  # gate -> reviewer comment to pass into the re-run of that stage
    decision: str
    halted: bool
    loops: int
    again: bool
    trigger_month: int | None


def _mod(name: str):
    return importlib.import_module(f"modelproof.{name}")


def _read(model_id: str, name: str) -> dict:
    p = config.ARTIFACTS / model_id / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _render(fn: str, *args) -> None:
    """HTML reports are WP3's job; a missing or failing renderer must never stop the pipeline."""
    try:
        getattr(_mod("report.render"), fn)(*args)
    except Exception as e:
        audit.append(
            "render.skipped", {"report": fn, "error": f"{type(e).__name__}: {e}"[:300]}, *args[:1]
        )


# ---------------------------------------------------------------- gate payloads (read only)
def _summary(gate: str, m: str) -> str:
    if gate == "discovery":
        r = inventory.get(m)
        return (
            f"{r.name}: tier {r.risk_tier} (materiality {r.materiality}, complexity {r.complexity}), "
            f"documentation {r.documentation_status}, {len(r.doc_code_drifts)} verified drift(s), "
            f"{len(r.security_flags)} security flag(s)"
        )
    if gate == "documentation":
        d = _read(m, "documentation.json")
        claims = d.get("claims", [])
        ok = sum(c["status"] == "supported" for c in claims)
        return f"grounding {d.get('grounding_score', 0):.0%}: {ok}/{len(claims)} claims supported"
    if gate == "redevelopment":
        c = _read(m, "parity_certificate.json")
        levels = ", ".join(
            f"{x['level']} {'pass' if x['passed'] else 'FAIL'}" for x in c.get("levels", [])
        )
        return f"parity {c.get('overall', 'n/a')} after attempt {c.get('attempt', '?')}: {levels}"
    v = _read(m, "validation_report.json")
    tests = v.get("results", {}).get("tests", [])
    mix = Counter(t["rag"] for t in tests)
    return f"rating {v.get('rating', 'n/a')}; {len(tests)} tests: " + ", ".join(
        f"{mix[k]} {k}" for k in ("green", "amber", "red")
    )


def _artifacts(gate: str, m: str) -> list[str]:
    paths = [f.format(m=m) for f in ARTIFACT_FILES[gate]]
    return [p for p in paths if (config.ARTIFACTS / p).exists()]


def _auto_decision(gate: str, m: str) -> dict:
    """--auto-approve never claims a human approved, and never promotes a failed parity certificate."""
    d = {
        "decision": "approve",
        "reviewer": AUTO_REVIEWER,
        "auto": True,
        "comment": "auto-approved (demo flag)",
    }
    if gate == "redevelopment" and _read(m, "parity_certificate.json").get("overall") != "PASS":
        d |= {
            "decision": "reject",
            "comment": "parity certificate is not PASS: a failed rebuild is not promoted",
        }
    return d


def _record(m: str, ap: Approval) -> None:
    rec = inventory.get(m)
    upd: dict = {"approvals": [*rec.approvals, ap]}
    if ap.decision == "approve" and ap.gate in STATUS_AFTER:
        upd["status"] = STATUS_AFTER[ap.gate]
        if ap.gate == "validation":
            upd |= {
                "last_validated": ap.ts.date(),
                "next_validation_due": _mod("tiering").next_due(rec.risk_tier, ap.ts.date()),
            }
    inventory.update(m, **upd)
    audit.append(f"gate.{ap.decision}", ap.model_dump(mode="json"), model_id=m, actor=ap.reviewer)
    _render("inventory")


# ---------------------------------------------------------------- nodes
def timed(stage: str):
    """Append wall time of a stage node to artifacts/runs/<run_id>/timings.jsonl (read by the benchmark)."""

    def deco(fn):
        def wrapper(s: State) -> dict:
            t0 = time.perf_counter()
            out = fn(s)
            d = config.ARTIFACTS / "runs" / llm.run_id()
            d.mkdir(parents=True, exist_ok=True)
            line = {
                "model_id": s["model_id"],
                "stage": stage,
                "seconds": round(time.perf_counter() - t0, 3),
            }
            with open(d / "timings.jsonl", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(line | {"llm_mode": os.environ.get("LLM_MODE") or "auto"}) + "\n"
                )
            return out

        return wrapper

    return deco


def _comment(s: State, gate: str) -> str:
    return s.get("feedback", {}).get(gate, "")


@timed("discover")
def n_discover(s: State) -> dict:
    m = s["model_id"]
    with llm.for_model(m):
        _mod("agents.discover").run(m, reviewer_comment=_comment(s, "discovery"))
    _render("inventory")
    return {}


@timed("document")
def n_document(s: State) -> dict:
    m = s["model_id"]
    with llm.for_model(m):
        _mod("agents.document").run(m, reviewer_comment=_comment(s, "documentation"))
    _render("documentation", m)
    return {}


@timed("redevelop")
def n_redevelop(s: State) -> dict:
    m = s["model_id"]
    with llm.for_model(m):
        cert = _mod("agents.redevelop").run(m, reviewer_comment=_comment(s, "redevelopment"))
    (config.artifact_dir(m) / "parity_certificate.json").write_text(
        cert.model_dump_json(indent=2) + "\n"
    )
    _render("parity", m)
    return {}


@timed("validate")
def n_validate(s: State) -> dict:
    m = s["model_id"]
    with llm.for_model(m):
        _mod("agents.validate").run(m, reviewer_comment=_comment(s, "validation"))
    try:
        _mod("tracking").log(m)
    except Exception as e:  # tracking is optional
        audit.append("tracking.skipped", {"error": f"{type(e).__name__}: {e}"[:300]}, m)
    return {}


@timed("monitor")
def n_monitor(s: State) -> dict:
    m, loops = s["model_id"], s.get("loops", 0)
    holdout = _mod("data").load_cr_pd_002("holdout")
    fn = _mod("parity").score_fn(config.REBUILT / "cr_pd_002.py")
    res = _mod("monitoring").simulate(m, holdout, fn, months=6)
    trig = res.trigger_month
    if trig is None:
        inventory.update(m, status="monitored")
        audit.append("monitoring.completed", {"trigger_month": None, "simulated": res.simulated}, m)
    else:
        inventory.update(m, status="revalidation_required")
        audit.append(
            "monitoring.trigger",
            {"trigger_month": trig, "simulated": res.simulated, "revalidation_cycle": loops + 1},
            m,
        )
    again = trig is not None and loops == 0  # revalidate once, then stop
    return {"trigger_month": trig, "again": again, "loops": loops + int(again)}


def gate_node(gate: str):
    def node(s: State) -> dict:
        m = s["model_id"]
        if s.get("auto"):
            d = _auto_decision(gate, m)
        else:
            d = interrupt(
                {
                    "gate": gate,
                    "model_id": m,
                    "summary": _summary(gate, m),
                    "artifacts": _artifacts(gate, m),
                }
            )
        ap = Approval(
            gate=gate,
            decision=d["decision"],
            reviewer=d.get("reviewer") or "reviewer",
            comment=d.get("comment", ""),
            ts=datetime.now(UTC),
            auto=bool(d.get("auto", False)),
        )
        _record(m, ap)
        fb = {**s.get("feedback", {}), gate: ap.comment if ap.decision == "reject" else ""}
        return {
            "decision": ap.decision,
            "feedback": fb,
            "halted": ap.decision == "reject" and bool(s.get("auto")),
        }

    return node


def _route(ok: str, back: str):
    def route(s: State) -> str:
        if s["decision"] == "approve":
            return ok
        return END if s.get("halted") else back

    return route


def build(model_id: str, checkpointer=None):
    g = StateGraph(State)
    g.add_node("discover", n_discover)
    g.add_node("document", n_document)
    for gate in ("discovery", "documentation"):
        g.add_node(f"gate_{gate}", gate_node(gate))
    g.add_edge(START, "discover")
    g.add_edge("discover", "gate_discovery")
    g.add_conditional_edges(
        "gate_discovery", _route("document", "discover"), ["document", "discover", END]
    )
    g.add_edge("document", "gate_documentation")
    full = model_id == config.REBUILD_TARGET
    g.add_conditional_edges(
        "gate_documentation",
        _route("redevelop" if full else END, "document"),
        ["redevelop" if full else END, "document", END],
    )
    if full:
        g.add_node("redevelop", n_redevelop)
        g.add_node("validate", n_validate)
        g.add_node("monitor", n_monitor)
        for gate in ("redevelopment", "validation"):
            g.add_node(f"gate_{gate}", gate_node(gate))
        g.add_edge("redevelop", "gate_redevelopment")
        g.add_conditional_edges(
            "gate_redevelopment", _route("validate", "redevelop"), ["validate", "redevelop", END]
        )
        g.add_edge("validate", "gate_validation")
        g.add_conditional_edges(
            "gate_validation", _route("monitor", "validate"), ["monitor", "validate", END]
        )
        g.add_conditional_edges(
            "monitor", lambda s: "validate" if s["again"] else END, ["validate", END]
        )
    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------- threads and public API
def _threads_path():
    return config.ARTIFACTS / "threads.json"


def _threads() -> dict:
    p = _threads_path()
    return json.loads(p.read_text()) if p.exists() else {}


def _save_thread(tid: str, **fields) -> None:
    t = _threads()
    t[tid] = {**t.get(tid, {}), **fields}
    _threads_path().parent.mkdir(parents=True, exist_ok=True)
    _threads_path().write_text(json.dumps(t, indent=2, sort_keys=True) + "\n")


def _drive(model_id: str, tid: str, payload) -> dict:
    """Run or resume a thread until it ends or reaches the next gate; keep threads.json current."""
    cfg = {"configurable": {"thread_id": tid}, "recursion_limit": 100}
    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(config.ARTIFACTS / "checkpoints.sqlite")) as saver:
        graph = build(model_id, saver)
        graph.invoke(payload, cfg)
        st = graph.get_state(cfg)
    gates = [i.value for t in st.tasks for i in t.interrupts]
    rec = inventory.get(model_id)
    out = {"thread_id": tid, "model_id": model_id, "inventory_status": rec.status if rec else None}
    if st.next and gates:
        out |= {"status": "waiting", **{k: gates[0][k] for k in ("gate", "summary", "artifacts")}}
        _save_thread(
            tid,
            model_id=model_id,
            state="pending",
            **{k: gates[0][k] for k in ("gate", "summary", "artifacts")},
        )
    else:
        out["status"] = "halted" if st.values.get("halted") else "completed"
        _save_thread(tid, model_id=model_id, state="done", result=out["status"])
    return out


def run(model_id: str, auto_approve: bool = False) -> dict:
    """Start a run. Without auto_approve it returns at the first gate (status "waiting")."""
    if model_id not in config.MODELS:
        raise ValueError(f"unknown model {model_id!r}; expected one of {list(config.MODELS)}")
    tid = f"{model_id}:{llm.run_id()}"
    audit.append("run.started", {"thread_id": tid, "auto_approve": auto_approve}, model_id)
    return _drive(
        model_id, tid, {"model_id": model_id, "auto": auto_approve, "feedback": {}, "loops": 0}
    )


def pending_gates() -> list[dict]:
    return [
        {"thread_id": tid, **{k: t.get(k) for k in ("model_id", "gate", "summary", "artifacts")}}
        for tid, t in _threads().items()
        if t.get("state") == "pending"
    ]


def resume(thread_id: str, decision: str, comment: str, reviewer: str) -> dict:
    if decision not in ("approve", "reject"):
        raise ValueError(f"decision must be approve or reject, got {decision!r}")
    if _threads().get(thread_id, {}).get("state") != "pending":
        raise ValueError(f"no pending gate for thread {thread_id!r}")
    model_id = thread_id.split(":", 1)[0]
    return _drive(
        model_id,
        thread_id,
        Command(resume={"decision": decision, "comment": comment, "reviewer": reviewer}),
    )
