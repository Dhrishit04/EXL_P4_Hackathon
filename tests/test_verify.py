import pytest

from modelproof.agents.verify import verify
from modelproof.schemas import Claim, Evidence, Facts

EXCERPT = "cutoff <- 0.50\nbins <- 10\nscore <- 600 - 20 * log(pd)\nif (pd > cutoff) decision <- 'decline'"
FACTS = Facts(
    model_id="CR-PD-002",
    language="R",
    files=[{"path": "model.R", "sha256": "h", "n_lines": 120, "kind": "code"}],
    datasets_read=["taiwan_defaults"],
    variables_created=["score", "decision"],
    variables_used=["pd", "LIMIT_BAL", "PAY_0"],
    dead_variables=["tmp_flag"],
    target="DEFAULT",
    parameters={
        "cutoff": {"value": 0.5, "evidence_id": "E1"},
        "bins": {"value": 10, "evidence_id": "E1"},
    },
    evidence=[
        Evidence(id="E1", kind="code", path="model.R", line_start=1, line_end=4, excerpt=EXCERPT),
        Evidence(
            id="E2", kind="doc", path="README.txt", line_start=1, line_end=1, excerpt="Cut-off 0.50"
        ),
    ],
)
METRICS = {"gini": {"value": 0.52134, "details": {"default_rate": 0.0512}}, "ks": {"value": 41.27}}


def one(text, ids=("E1",), metrics=None, facts=FACTS):
    out, g = verify(
        [Claim(section="3 Methodology", text=text, evidence_ids=list(ids))], facts, metrics
    )
    return out[0], g


@pytest.mark.parametrize(
    "text",
    [
        "The model applies a `cutoff` of 0.5 and creates `score`.",
        "Applications with `pd` above 0.50 are declined (`decision`).",
        "The score is built from 600 and 20.",
        "The script has 120 lines and reads `taiwan_defaults` and `PAY_0`.",
        "Reviewed on 2026-11-13 under SS1/23 for CR-PD-002, first drafted in 2024.",
        "1. The `bins` parameter is 10.",
    ],
)
def test_supported(text):
    c, g = one(text)
    assert c.status == "supported", c.reason
    assert c.reason == "" and g == 1.0


@pytest.mark.parametrize(
    "text, ids, needle",
    [
        ("The model applies a cutoff.", (), "no evidence ids"),
        ("The model applies a cutoff.", ("E9",), "unknown evidence ids"),
        ("It uses `phantom_var` as input.", ("E1",), "identifiers not found"),
        ("It uses debt_to_income as input.", ("E1",), "identifiers not found"),
        ("The score uses 37 bins.", ("E1",), "numbers not traceable"),
    ],
)
def test_unsupported(text, ids, needle):
    c, g = one(text, ids)
    assert c.status == "unsupported" and needle in c.reason and g == 0.0


def test_unbackticked_snake_case_in_facts_and_file_names_are_fine():
    c, _ = one("Dead code: tmp_flag is never used; results go to validation_results.json.")
    assert c.status == "supported", c.reason


def test_rounding_percent_and_metric_ids():
    for text, ok in [
        ("Gini is 0.52.", True),
        ("Gini is 0.521.", True),
        ("Gini is 0.53.", False),
        ("The default rate is 5.1%.", True),
        ("The default rate is 9%.", False),
        ("KS is 41.3.", True),
        ("KS is 41.27.", True),
    ]:
        c, _ = one(text, ("gini", "ks"), METRICS)
        assert (c.status == "supported") is ok, (text, c.reason)


def test_contradicted_parameter_value():
    c, g = one("The `cutoff` is 0.6.")
    assert c.status == "contradicted" and "`cutoff` is 0.5" in c.reason and g == 0.0
    c, _ = one("The cutoff is set to 10 and `bins` is 5.")
    assert c.status == "contradicted"


def test_grounding_keeps_unsupported_and_does_not_mutate():
    claims = [
        Claim(section="a", text="`cutoff` is 0.5.", evidence_ids=["E1"]),
        Claim(section="b", text="Made up 99.", evidence_ids=["E1"]),
        Claim(section="c", text="No evidence."),
    ]
    out, g = verify(claims, FACTS)
    assert len(out) == 3 and g == pytest.approx(1 / 3)
    assert [c.status for c in out] == ["supported", "unsupported", "unsupported"]
    assert all(c.status == "unsupported" for c in claims)  # inputs untouched


def test_no_claims_is_fully_grounded():
    assert verify([], FACTS) == ([], 1.0)


def test_metric_keys_are_valid_evidence_without_facts_evidence():
    facts = Facts(model_id="M", language="R", files=[])
    c, _ = one("Gini is 0.52.", ("gini",), METRICS, facts)
    assert c.status == "supported", c.reason
    c, _ = one("Gini is 0.52.", ("gini",), None, facts)
    assert c.status == "unsupported"
