import json

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from modelproof import config
from modelproof.schemas import CheckResult, ValidationResults
from modelproof.validation import _rag, rating, run_suite, scored_rows


def sample_rows(n=400):
    rng = np.random.default_rng(42)
    frame = pd.DataFrame({"ID": np.arange(n), "BILL_AMT1": rng.uniform(100, 100000, n),
                          "LIMIT_BAL": rng.uniform(10000, 200000, n), "PAY_0": rng.integers(0, 4, n),
                          "SEX": rng.integers(1, 3, n), "AGE": rng.integers(21, 80, n),
                          "MARRIAGE": rng.integers(1, 4, n), "EDUCATION": rng.integers(1, 4, n)})
    frame["DEFAULT"] = rng.binomial(1, scorer(frame)["pd"])
    return frame


def scorer(frame):
    p = expit(-2 + 0.6 * frame.PAY_0 + frame.BILL_AMT1 / 100000 - frame.LIMIT_BAL / 200000)
    return pd.DataFrame({"ID": frame.ID, "pd": p, "score": 600 - 100 * p,
                         "grade": np.where(p < 0.3, "A", "B"),
                         "decision": np.where(p < 0.3, "approve", "reject")})


def test_suite_roundtrip_and_all_areas():
    frame = sample_rows()
    result = run_suite("CR-PD-002", frame.iloc[:250], frame.iloc[250:], scorer,
                       ["BILL_AMT1", "LIMIT_BAL", "PAY_0"])
    assert {test.area for test in result.tests} == {"discrimination", "calibration", "stability", "conceptual", "benchmark", "sensitivity", "fairness", "data_quality", "implementation"}
    path = config.artifact_dir("CR-PD-002") / "validation_results.json"
    assert ValidationResults.model_validate_json(path.read_text()).model_dump() == result.model_dump()
    assert next(t for t in result.tests if t.test == "parity").rag == "amber"
    assert all(t.rag in {"green", "amber", "red"} for t in result.tests)
    json.loads(path.read_text(), parse_constant=lambda value: pytest.fail(f"Nonfinite {value}"))


def test_scoring_rejects_missing_and_duplicate_ids():
    frame = sample_rows(20)
    with pytest.raises(ValueError, match="exactly match"):
        scored_rows(frame, lambda rows: scorer(rows).iloc[:-1])
    with pytest.raises(ValueError, match="unique IDs"):
        scored_rows(frame, lambda rows: pd.concat([scorer(rows), scorer(rows).iloc[:1]]))


def test_score_alignment_uses_ids():
    frame = sample_rows(20)
    assert scored_rows(frame, scorer).equals(scored_rows(frame, lambda rows: scorer(rows).iloc[::-1]))


@pytest.mark.parametrize("rags, expected", [(["green"], "Fit for use"), (["amber"], "Fit with conditions"), (["red"], "Fit with conditions"), (["red", "red"], "Not fit")])
def test_rating_policy(rags, expected):
    checks = [CheckResult(test="x", area="implementation", value=0, threshold="test", rag=rag) for rag in rags]
    assert rating(checks) == expected


@pytest.mark.parametrize("value,expected", [(0.09, "green"), (0.1, "amber"), (0.249, "amber"), (0.25, "red"), (None, "amber"), (np.nan, "amber")])
def test_lower_policy_boundaries(value, expected):
    assert _rag(value, {"green": 0.1, "amber": 0.25}) == expected


@pytest.mark.parametrize("value,expected", [(0.4, "green"), (0.3, "amber"), (0.29, "red")])
def test_higher_policy_boundaries(value, expected):
    assert _rag(value, {"green": 0.4, "amber": 0.3}, higher=True) == expected
