import numpy as np
import pandas as pd
import pytest
from scipy import stats

from modelproof import metrics as m


def test_known_ranking():
    assert m.auc([0, 0, 1, 1], [.1, .2, .8, .9]) == 1
    assert m.gini([0, 1], [.1, .9]) == 1
    assert m.ks([0, 1], [.1, .9]) == 1
    assert m.brier([0, 1], [0, 1]) == 0
    assert m.auc([0, 1], [.5, .5]) == .5


def test_distribution_metrics():
    assert m.psi(np.arange(100), np.arange(100)) == 0
    assert m.psi([1, 1, 1], [2, 2, 2]) > 0
    assert m.psi(["a", "b"], ["a", "b"]) == 0
    assert m.hhi(pd.Series(["a", "a", "b", "b"])) == .5


def test_jeffreys():
    frame = pd.DataFrame({"grade": ["A"] * 10, "pd": [.1] * 10, "DEFAULT": [1] * 3 + [0] * 7})
    result = m.jeffreys_by_grade(frame).iloc[0]
    assert result.p == pytest.approx(stats.beta.cdf(.1, 3.5, 7.5))
    assert result.N == 10


def test_hl_hand_calculation():
    y = [0, 0, 0, 1, 1, 1]
    p = [.1, .1, .5, .5, .9, .9]
    statistic, probability = m.hosmer_lemeshow(y, p, groups=3)
    expected = 2 * (.2 ** 2 / .18)
    assert statistic == pytest.approx(expected)
    assert probability == pytest.approx(stats.chi2.sf(expected, 1))


def test_vif_and_bootstrap():
    rng = np.random.default_rng(42)
    values = pd.DataFrame(rng.normal(size=(10000, 2)), columns=["a", "b"])
    assert all(1 <= value < 1.01 for value in m.vif(values).values())
    assert m.bootstrap_ci(m.auc, [0, 0, 1, 1], [.1, .2, .8, .9], n=30) == (1, 1)


def test_invalid_probabilities():
    with pytest.raises(ValueError):
        m.brier([0, 1], [2, -1])


@pytest.mark.parametrize("alpha", [0, 1, -0.1, float("nan"), float("inf")])
def test_jeffreys_rejects_invalid_significance(alpha):
    frame = pd.DataFrame({"grade": ["A", "A"], "DEFAULT": [0, 1], "pd": [0.2, 0.3]})
    with pytest.raises(ValueError, match="alpha"):
        m.jeffreys_by_grade(frame, alpha=alpha)

