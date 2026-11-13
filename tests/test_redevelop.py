import json
from pathlib import Path

import pytest

from modelproof import audit, config, llm
from modelproof.agents import redevelop

REFERENCE = (Path(__file__).parent / "fixtures" / "cr_pd_002_reference.py").read_text()
NAIVE = REFERENCE.replace('np.searchsorted(CUT_UTIL, f.util.to_numpy(), side="left")', 'np.searchsorted(CUT_UTIL, f.util.to_numpy(), side="right")')
GOOD_TEST = "import pandas as pd\nimport cr_pd_002 as m\n\n\ndef test_util():\n    df = pd.DataFrame({'BILL_AMT1': [50000], 'LIMIT_BAL': [100000], 'ID': [1], 'PAY_AMT1': [0], 'AGE': [30], " \
            + "'PAY_0': [0], 'PAY_2': [0], 'PAY_3': [0], 'PAY_4': [0], 'PAY_5': [0], 'PAY_6': [0]})\n    assert m.build_features(df).util[0] == 0.5\n"


class FakeLLM:
    """Replaces llm.structured: hands out the scripted bundles in order and records every prompt."""

    def __init__(self, bundles):
        self.bundles, self.calls = list(bundles), []

    def __call__(self, system, user, schema, task):
        self.calls.append({"system": system, "user": user, "task": task})
        llm.assert_no_row_data(user)  # the real structured() enforces this too
        return self.bundles[min(len(self.calls), len(self.bundles)) - 1]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REBUILT", tmp_path / "rebuilt")

    def install(*bundles):
        fake = FakeLLM([redevelop.CodeBundle(module_code=m, test_code=t, notes="n") for m, t in bundles])
        monkeypatch.setattr(llm, "structured", fake)
        return fake

    return install


def attempts():
    return sorted((config.ARTIFACTS / "CR-PD-002" / "redevelop").glob("attempt_*"))


def test_broken_first_attempt_is_repaired_from_the_localiser_summary(setup):
    fake = setup((NAIVE, GOOD_TEST), (REFERENCE, GOOD_TEST))
    cert = redevelop.run(reviewer_comment="please keep the audit trail")
    assert cert.overall == "PASS" and cert.attempt == 2
    first, second = (c["user"] for c in fake.calls)
    assert '<untrusted_source path="legacy_estate/CR-PD-002_r_card_default_pd/pd_model.R">' in first
    assert "LIMIT_BAL" in first and "int64" in first and "please keep the audit trail" in first
    assert "all exactly at cut point" in second and '"util"' in second  # localiser summary only
    assert "Traceback" not in second and fake.calls[0]["task"] == "redevelop"
    for a in attempts():  # the attempt history is kept
        assert {p.name for p in a.iterdir()} >= {"cr_pd_002.py", "test_cr_pd_002.py", "certificate.json", "test_output.txt"}
    assert [json.loads((a / "certificate.json").read_text())["overall"] for a in attempts()] == ["FAIL", "PASS"]
    assert (config.REBUILT / "cr_pd_002.py").read_text() == REFERENCE
    assert (config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").exists()
    events = [e["event"] for e in audit.read() if e["model_id"] == "CR-PD-002"]
    assert events.count("redevelop.attempt") == 2 and "redevelop.completed" in events and audit.verify_chain()


def test_sandbox_violations_are_never_executed_and_are_fed_back(setup):
    fake = setup(("import os\nos.environ['PWNED'] = '1'\n" + REFERENCE, GOOD_TEST), (REFERENCE, GOOD_TEST))
    cert = redevelop.run()
    assert cert.overall == "PASS" and "import os is not allowed" in fake.calls[1]["user"]
    first = json.loads((attempts()[0] / "certificate.json").read_text())
    assert first["overall"] == "FAIL" and "sandbox_violations" in first["mismatch_summary"]
    import os

    assert "PWNED" not in os.environ


def test_failing_generated_tests_block_parity_and_are_fed_back(setup):
    fake = setup((REFERENCE, "def test_x():\n    assert 1 == 2\n"), (REFERENCE, GOOD_TEST))
    cert = redevelop.run()
    assert cert.overall == "PASS" and "assert 1 == 2" in fake.calls[1]["user"]
    assert json.loads((attempts()[0] / "certificate.json").read_text())["mismatch_summary"] == {"tests_failed": True}


def test_out_of_attempts_returns_the_failing_certificate_and_writes_no_rebuilt_module(setup):
    setup((NAIVE, GOOD_TEST))
    cert = redevelop.run(max_attempts=2)
    assert cert.overall == "FAIL" and cert.attempt == 2 and len(attempts()) == 2
    assert not (config.REBUILT / "cr_pd_002.py").exists()
    assert json.loads((config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").read_text())["attempt"] == 2


def test_generated_tests_that_import_pytest_are_blocked_before_anything_runs(setup):
    sneaky = "import pytest\n\ndef test_x():\n    pytest.importorskip('os')\n"
    fake = setup((REFERENCE, sneaky), (REFERENCE, GOOD_TEST))
    assert redevelop.run().overall == "PASS" and "import pytest is not allowed" in fake.calls[1]["user"]
