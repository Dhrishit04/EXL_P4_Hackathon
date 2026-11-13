import pandas as pd
import pytest

from modelproof.fairness import report


def test_approval_semantics_and_group_auc():
    data = pd.DataFrame({"DEFAULT": [0, 1, 0, 1], "approved": [1, 0, 1, 0],
                         "pd": [.1, .9, .2, .8], "SEX": [1, 1, 2, 2]})
    result = report(data, "DEFAULT", "approved", "pd", ["SEX"])
    assert result["worst_dp_ratio"] == 1
    assert result["worst_eod"] == 0
    assert all(row["auc"] == 1 for row in result["by_group"])
    assert all(row["tpr"] == 1 for row in result["by_group"])
    assert all(row["fpr"] == 0 for row in result["by_group"])


def test_undefined_rates_are_explicit():
    data = pd.DataFrame({"DEFAULT": [0, 0], "approved": [0, 0], "pd": [.1, .2], "SEX": [1, 2]})
    result = report(data, "DEFAULT", "approved", "pd", ["SEX"])
    assert result["worst_dp_ratio"] is None
    assert result["worst_eod"] is None
    assert result["by_group"][0]["auc"] is None


def test_invalid_outcome():
    with pytest.raises(ValueError):
        report(pd.DataFrame({"y": [2], "a": [1]}), "y", "a", "p", [])
