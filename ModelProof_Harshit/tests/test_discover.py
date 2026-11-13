import sys
import types
from datetime import UTC, date, datetime

import pytest

import modelproof
from modelproof import audit, config, inventory, llm
from modelproof.agents import discover
from modelproof.schemas import Approval, Evidence, Facts, Finding, InventoryRecord

DOC = Evidence(
    id="E1",
    kind="doc",
    path="doc.md",
    line_start=3,
    line_end=3,
    excerpt="The approval cut-off score is 600.",
)
CODE = Evidence(
    id="E2", kind="code", path="m.sas", line_start=9, line_end=9, excerpt="cutoff = 620;"
)
CODE2 = Evidence(
    id="E3", kind="code", path="m.sas", line_start=11, line_end=11, excerpt="age_n = age / 10;"
)
FILES_DOC = [
    {"path": "m.sas", "sha256": "a", "n_lines": 20, "kind": "code"},
    {"path": "doc.md", "sha256": "b", "n_lines": 5, "kind": "doc"},
]
FILES_NODOC = FILES_DOC[:1]


def facts(model_id, deps=(), files=FILES_DOC, evidence=(DOC, CODE, CODE2)):
    return Facts(
        model_id=model_id,
        language="SAS",
        files=files,
        datasets_read=["german"],
        dependencies=list(deps),
        evidence=list(evidence),
    )


def semantic(candidates=None, **kw):
    cands = (
        candidates
        if candidates is not None
        else [
            discover._Candidate(
                field="cutoff",
                doc_value="600",
                code_value="620",
                doc_evidence_id="E1",
                code_evidence_id="E2",
            ),
            discover._Candidate(
                field="cutoff",
                doc_value="700",
                code_value="620",
                doc_evidence_id="E1",
                code_evidence_id="E2",
            ),  # not in doc line
            discover._Candidate(
                field="cutoff",
                doc_value="620",
                code_value="620",
                doc_evidence_id="E1",
                code_evidence_id="E2",
            ),  # equal / not in doc
            discover._Candidate(
                field="cutoff",
                doc_value="cutoff",
                code_value="600",
                doc_evidence_id="E2",
                code_evidence_id="E1",
            ),  # kinds swapped
            discover._Candidate(
                field="cutoff",
                doc_value="600",
                code_value="620",
                doc_evidence_id="E1",
                code_evidence_id="NOPE",
            ),  # unknown id
        ]
    )
    base = dict(
        name="Scorecard", purpose="p", model_type="PD", materiality="H", complexity="H",
        features=[discover.Feature(name="age_n", transformation="/10", evidence_id="E3"),
                  discover.Feature(name="x", evidence_id="E99")],
        drift_candidates=cands, owner_role="Head of Credit Risk Modelling",
    )  # fmt: skip
    return discover._Semantic(**base | kw)


def fake_module(monkeypatch, name, **attrs):
    mod = types.ModuleType(f"modelproof.{name}")
    mod.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, f"modelproof.{name}", mod)
    monkeypatch.setattr(modelproof, name, mod, raising=False)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    table = {
        "CR-PD-001": facts("CR-PD-001"),
        "PR-RB-004": facts("PR-RB-004", deps=["cr_pd_001 scorecard output"]),
    }  # FR-TX-003 / CR-PD-002 raise: an undiscoverable sibling must be tolerated

    def facts_for(model_id):
        return table[model_id]

    calls = {}
    fake_module(monkeypatch, "extract", facts_for=facts_for)
    fake_module(
        monkeypatch,
        "security",
        scan=lambda m: [
            Finding(
                id="SEC-1",
                model_id=m,
                area="security",
                severity="high",
                ss123_principle="P3",
                description="injection",
            )
        ],
    )
    fake_module(
        monkeypatch, "tiering", assign=lambda m, c: 3, next_due=lambda tier, lv: date(2029, 1, 1)
    )

    def fake_structured(system, user, schema, task):
        calls.update(system=system, user=user, schema=schema, task=task)
        return calls["response"]

    calls["response"] = semantic()
    monkeypatch.setattr(llm, "structured", fake_structured)
    return types.SimpleNamespace(table=table, calls=calls, path=tmp_path)


def test_discover_end_to_end(env):
    rec = discover.run("CR-PD-001")
    # only the one genuine drift survives the deterministic check, and is marked verified
    assert [(d.doc_value, d.code_value, d.verified) for d in rec.doc_code_drifts] == [
        ("600", "620", True)
    ]
    assert rec.documentation_status == "outdated"
    # tier and due date come from tiering, never from the LLM's H/H proposal
    assert (rec.risk_tier, rec.next_validation_due) == (3, date(2029, 1, 1))
    assert (rec.materiality, rec.complexity) == ("H", "H")
    # deterministic fields
    assert (
        rec.platform_language == "SAS"
        and rec.input_data == ["german"]
        and rec.source_files == FILES_DOC
    )
    assert rec.security_flags[0].id == "SEC-1" and rec.status == "discovered"
    assert [(f.name, f.evidence_id) for f in rec.features] == [("age_n", "E3"), ("x", None)]
    assert rec.downstream_models == ["PR-RB-004"] and rec.upstream_models == []
    # persisted + audited
    assert inventory.get("CR-PD-001") == rec
    assert (env.path / "inventory" / "inventory.json").exists()
    last = audit.read()[-1]
    assert (
        last["event"] == "discover.completed"
        and last["actor"] == "agent:discover"
        and last["model_id"] == "CR-PD-001"
    )
    assert last["payload"]["drifts_proposed"] == 5 and last["payload"]["drifts_verified"] == 1
    assert audit.verify_chain()


def test_prompt_is_wrapped_untrusted_and_guarded(env):
    discover.run("CR-PD-001", reviewer_comment="Name the target variable.")
    c = env.calls
    assert c["task"] == "discover" and c["schema"] is discover._Semantic
    assert "untrusted_source" in c["system"]  # standing guard appended by load_prompt
    assert '<untrusted_source path="m.sas">\ncutoff = 620;' in c["user"]
    assert "[E1] doc.md:3-3 (doc)" in c["user"] and "Name the target variable." in c["user"]
    assert "Name the target variable." not in c["system"]


def test_no_reviewer_comment_no_rejection_text(env):
    discover.run("CR-PD-001")
    assert "rejected" not in env.calls["user"]


def test_upstream_from_dependencies(env):
    rec = discover.run("PR-RB-004")
    assert rec.upstream_models == ["CR-PD-001"] and rec.downstream_models == []


@pytest.mark.parametrize(
    ("files", "candidates", "expected"),
    [
        (
            FILES_NODOC,
            None,
            "missing",
        ),  # no doc file at all, even with a (bogus) valid-looking candidate
        (FILES_DOC, None, "outdated"),
        (FILES_DOC, [], "current"),
    ],
)
def test_documentation_status(env, files, candidates, expected):
    env.table["CR-PD-001"] = facts("CR-PD-001", files=files)
    env.calls["response"] = semantic(candidates=candidates)
    assert discover.run("CR-PD-001").documentation_status == expected


def test_rerun_keeps_approvals_and_last_validated(env):
    old = discover.run("CR-PD-001")
    appr = Approval(
        gate="discovery", decision="approve", reviewer="r", ts=datetime(2026, 11, 13, tzinfo=UTC)
    )
    inventory.upsert(
        old.model_copy(update={"approvals": [appr], "last_validated": date(2026, 1, 1)})
    )
    seen = []

    def next_due(tier, last_validated):
        seen.append(last_validated)
        return date(2029, 1, 1)

    sys.modules["modelproof.tiering"].next_due = next_due
    rec = discover.run("CR-PD-001")
    assert rec.approvals == [appr] and rec.last_validated == date(2026, 1, 1)
    assert seen == [date(2026, 1, 1)]
    assert len(inventory.load()) == 1  # upsert, not append


def test_verified_drifts_dedups_and_strips(env):
    c = discover._Candidate(
        field="f", doc_value=" 600 ", code_value="620 ", doc_evidence_id="E1", code_evidence_id="E2"
    )
    out = discover.verified_drifts([c, c], [DOC, CODE])
    assert len(out) == 1 and out[0].doc_value == "600" and out[0].code_value == "620"


def test_inventory_record_is_valid_schema(env):
    rec = discover.run("CR-PD-001")
    assert InventoryRecord.model_validate_json(rec.model_dump_json()) == rec
