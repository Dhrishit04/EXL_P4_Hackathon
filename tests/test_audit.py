import pytest

from modelproof import audit, config


@pytest.fixture(autouse=True)
def tmp_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    return tmp_path


def test_chain_verifies_then_breaks_on_edit(tmp_artifacts):
    assert audit.verify_chain()  # empty log is trivially valid
    hashes = [
        audit.append(f"e{i}", {"i": i, "nested": {"b": 1, "a": 2}}, model_id="M") for i in range(3)
    ]
    assert len(set(hashes)) == 3 and len(audit.read()) == 3
    assert audit.read()[1]["prev_hash"] == hashes[0]
    assert audit.verify_chain()

    p = tmp_artifacts / "audit" / "audit_log.jsonl"
    p.write_text(p.read_text().replace('"i":1', '"i":99').replace('"i": 1', '"i": 99'))
    assert not audit.verify_chain()


def test_deleting_an_entry_breaks_chain(tmp_artifacts):
    for i in range(3):
        audit.append("e", {"i": i})
    p = tmp_artifacts / "audit" / "audit_log.jsonl"
    first, _, last = p.read_text().splitlines()
    p.write_text(first + "\n" + last + "\n")
    assert not audit.verify_chain()


def test_payload_with_models_and_dates(tmp_artifacts):
    from datetime import date

    from modelproof.schemas import Feature

    audit.append("x", {"f": Feature(name="a"), "d": date(2026, 1, 1)}, actor="tester")
    assert audit.read()[0]["payload"]["f"]["name"] == "a" and audit.verify_chain()
