"""Real extractors, scanner, tiering, renderer and graph; only the LLM is scripted.
Catches wiring bugs between the work packages without an API key."""

import re

import pytest

from modelproof import audit, config, extract, graph, inventory, llm

TYPES = {"CR-PD-001": "PD", "CR-PD-002": "PD", "FR-TX-003": "fraud", "PR-RB-004": "pricing"}


def _model_in(prompt: str) -> str:
    return re.search(r"[A-Z]{2}-[A-Z]{2}-\d{3}", prompt).group(0)


def _evidence_with(facts, kind: str, text: str):
    return next((e for e in facts.evidence if e.kind == kind and text in e.excerpt), None)


@pytest.fixture
def scripted_llm(monkeypatch):
    def structured(system, user, schema, task):
        mid = _model_in(user)
        if task == "discover":
            facts = extract.facts_for(mid)
            doc, code = _evidence_with(facts, "doc", "520"), _evidence_with(facts, "code", "540")
            drifts = []
            if mid == "CR-PD-001" and doc and code:  # one real seeded drift and one fabricated
                drifts = [
                    dict(field="cutoff", doc_value="520", code_value="540", doc_evidence_id=doc.id, code_evidence_id=code.id),
                    dict(field="fake", doc_value="999", code_value="111", doc_evidence_id=doc.id, code_evidence_id=code.id),
                ]  # fmt: skip
            return schema(
                name=f"{mid} model",
                model_type=TYPES[mid],
                materiality="M",
                complexity="L",
                drift_candidates=drifts,
            )
        facts = extract.facts_for(mid)
        ids = [e.id for e in facts.evidence[:2]]
        return schema(claims=[
            dict(section="1 Purpose and use", text="This model scores applicants.", evidence_ids=ids),
            dict(section="7 Performance at development", text="The AUC is 0.93.", evidence_ids=ids),
        ])  # fmt: skip

    monkeypatch.setattr(llm, "structured", structured)


def test_discover_all_models_with_real_modules(scripted_llm):
    from modelproof.agents import discover

    recs = {m: discover.run(m) for m in config.MODELS}
    assert [r.model_id for r in inventory.load()] == list(config.MODELS)
    assert recs["FR-TX-003"].documentation_status == "missing"
    assert recs["CR-PD-001"].upstream_models == [] and recs["CR-PD-001"].downstream_models == [
        "PR-RB-004"
    ]
    assert recs["PR-RB-004"].upstream_models == ["CR-PD-001"]
    assert {m for m, r in recs.items() if r.security_flags} == {
        "PR-RB-004"
    }  # the seeded injection, only there
    assert all(
        r.risk_tier == 3 for r in recs.values()
    )  # materiality M + complexity L, from tiering not the LLM
    drifts = recs["CR-PD-001"].doc_code_drifts
    assert [(d.doc_value, d.code_value, d.verified) for d in drifts] == [("520", "540", True)]
    assert recs["CR-PD-001"].documentation_status == "outdated"
    assert audit.verify_chain()


def test_document_grades_claims_against_real_evidence(scripted_llm):
    from modelproof.agents import discover, document

    discover.run("CR-PD-001")
    doc = document.run("CR-PD-001")
    assert [c.status for c in doc.claims] == ["supported", "unsupported"]
    assert "0.93" in doc.claims[1].reason and doc.grounding_score == 0.5
    assert [d.field for d in doc.drifts] == ["cutoff"]
    assert (config.ARTIFACTS / "CR-PD-001" / "documentation.json").exists()


@pytest.mark.parametrize("model_id", ["CR-PD-001", "PR-RB-004"])
def test_graph_end_to_end_for_a_documented_model(scripted_llm, model_id):
    r = graph.run(model_id, auto_approve=True)
    assert r["status"] == "completed" and r["inventory_status"] == "documented"
    art = config.ARTIFACTS
    for f in (
        f"{model_id}/facts.json",
        f"{model_id}/documentation.json",
        f"{model_id}/documentation.html",
        "inventory/inventory.html",
    ):
        assert (art / f).exists(), f
    assert not any(e["event"] == "render.skipped" for e in audit.read())
    assert audit.verify_chain()
    rec = inventory.get(model_id)
    assert [(a.gate, a.auto) for a in rec.approvals] == [
        ("discovery", True),
        ("documentation", True),
    ]
