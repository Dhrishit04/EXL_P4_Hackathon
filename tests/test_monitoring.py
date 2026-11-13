import numpy as np
import pytest
from modelproof.schemas import MonitoringResult
from test_validation import sample_rows, scorer

from modelproof import config
from modelproof.monitoring import simulate


def test_monitoring_reproducible_and_saved():
    frame = sample_rows()
    before = frame.copy(deep=True)
    result = simulate("CR-PD-002", frame, scorer)
    assert result == simulate("CR-PD-002", frame, scorer)
    assert result.simulated and len(result.points) == 6
    assert frame.equals(before)
    expected = next((point.month for point in result.points if point.breaches), None)
    assert result.trigger_month == expected
    out = config.artifact_dir("CR-PD-002")
    assert MonitoringResult.model_validate_json((out / "monitoring.json").read_text()) == result
    assert (out / "monitoring.png").read_bytes().startswith(b"\x89PNG")


@pytest.mark.parametrize("months", [0, 7, -1, 1.5])
def test_simulation_requires_documented_months(months):
    with pytest.raises(ValueError):
        simulate("CR-PD-002", sample_rows(), scorer, months)


def test_stress_schedule_and_observed_labels_are_preserved():
    frame = sample_rows()
    calls = []

    def spy(rows):
        calls.append(rows.copy())
        return scorer(rows)

    simulate("CR-PD-002", frame, spy)
    for month, rows in enumerate(calls[1:], start=1):
        rng = np.random.default_rng(42 + month)
        baseline = frame.iloc[rng.integers(0, len(frame), size=3000)].reset_index(drop=True)
        assert rows.DEFAULT.equals(baseline.DEFAULT)
        factor = {4: 1.15, 5: 1.30, 6: 1.50}.get(month, 1)
        np.testing.assert_allclose(rows.BILL_AMT1, baseline.BILL_AMT1 * factor)
        changed = rows.PAY_0.to_numpy() - baseline.PAY_0.to_numpy()
        assert np.isin(changed, [0, 1]).all()
        assert changed.sum() == {4: 300, 5: 600, 6: 900}.get(month, 0)
