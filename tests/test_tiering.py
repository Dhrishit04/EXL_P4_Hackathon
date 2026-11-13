from datetime import date

import pytest

from modelproof import tiering


@pytest.fixture(autouse=True)
def policy(monkeypatch):
    monkeypatch.setattr(tiering, "load_policy", lambda: {
        "tier_matrix": {"HH": 1, "HM": 1, "MH": 1, "HL": 2, "MM": 2, "LH": 2, "ML": 3, "LM": 3, "LL": 3},
        "validation_months_by_tier": {1: 12, 2: 24, 3: 36}})


def test_matrix():
    assert tiering.assign("H", "M") == 1
    assert tiering.assign("L", "L") == 3
    with pytest.raises(ValueError):
        tiering.assign("high", "L")


def test_calendar_months():
    assert tiering.next_due(1, date(2024, 2, 29)) == date(2025, 2, 28)
    assert tiering.next_due(2, date(2024, 1, 31)) == date(2026, 1, 31)
