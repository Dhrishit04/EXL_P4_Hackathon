"""Policy-driven model tier and calendar review dates."""
import calendar
from datetime import date

from modelproof.config import load_policy


def assign(materiality: str, complexity: str) -> int:
    if materiality not in {"H", "M", "L"} or complexity not in {"H", "M", "L"}:
        raise ValueError("Materiality and complexity must be H, M or L")
    return int(load_policy()["tier_matrix"][materiality + complexity])


def next_due(tier: int, last_validated: date | None) -> date:
    policy = load_policy()["validation_months_by_tier"]
    months = policy.get(tier, policy.get(str(tier)))
    if months is None:
        raise ValueError(f"Unknown tier {tier}")
    start = last_validated or date.today()
    year, month = divmod(start.year * 12 + start.month - 1 + int(months), 12)
    month += 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
