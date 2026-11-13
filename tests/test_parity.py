import json
import re
import shutil
from pathlib import Path

import pytest

from modelproof import config, data, parity

ADAPTER = Path(__file__).parent / "fixtures" / "golden_adapter.py"


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(parity.sandbox, "check_code", lambda code, allow=(): [])  # the replay adapter reads CSVs on purpose
    p = tmp_path / "attempt_1" / "cr_pd_002.py"
    p.parent.mkdir()
    shutil.copy(ADAPTER, p)
    return p


def perturbed(adapter: Path) -> Path:
    adapter.write_text(adapter.read_text().replace("PERTURB = False", "PERTURB = True"))
    return adapter


def test_goldens_compared_with_themselves_pass_all_five_levels(adapter):
    cert = parity.run(adapter, attempt=1, run_id="t1")
    assert cert.overall == "PASS" and [lv.level for lv in cert.levels] == ["L1", "L2", "L3", "L4", "L5"]
    assert all(lv.passed for lv in cert.levels) and cert.mismatch_summary == {}
    assert cert.versions["R"].startswith("R version") and {"python", "pandas", "numpy", "statsmodels"} <= set(cert.versions)
    assert {"python_module", "legacy_r:pd_model.R", "input:cr_pd_002_edge.csv", "golden:coefficients.csv"} <= set(cert.hashes)
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in cert.hashes.values())
    saved = json.loads((adapter.parent / "certificate.json").read_text())
    assert saved["overall"] == "PASS" and saved["attempt"] == 1 and saved["run_id"] == "t1"
    assert (config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").exists()  # PASS is final


def test_perturbed_copy_fails_and_the_localiser_names_the_cut_point_without_rows(adapter):
    cert = parity.run(perturbed(adapter), attempt=1, run_id="t2")
    by = {lv.level: lv for lv in cert.levels}
    assert cert.overall == "FAIL" and by["L1"].passed and by["L2"].passed
    assert not by["L3"].passed and not by["L4"].passed and not by["L5"].passed
    util = cert.mismatch_summary["util"]
    assert util["nearest_cut"] == 0.0 and util["pattern"] == "all exactly at cut point" and util["count"] > 0
    assert len(json.dumps(cert.mismatch_summary)) < 700  # counts and cut points only, never rows
    assert not (config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").exists()  # attempt 1 of 4 is not final


def test_last_attempt_is_final_even_when_it_fails(adapter):
    parity.run(perturbed(adapter), attempt=config.load_policy()["max_redevelop_attempts"], run_id="t3")
    assert json.loads((config.ARTIFACTS / "CR-PD-002" / "parity_certificate.json").read_text())["overall"] == "FAIL"


def test_a_module_that_does_not_load_fails_cleanly(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text("raise RuntimeError('boom')\n")
    cert = parity.run(p, attempt=1, run_id="t4")
    assert cert.overall == "FAIL" and "RuntimeError" in cert.mismatch_summary["error"] and "boom" not in cert.mismatch_summary["error"]
    assert not any(lv.passed for lv in cert.levels)


def test_score_fn_scores_raw_rows_with_golden_parameters(adapter):
    fn = parity.score_fn(adapter)
    raw = data.load_cr_pd_002("holdout").head(5)
    out = fn(raw)
    assert list(out.columns) == ["ID", "pd", "score", "grade", "decision"] and out.ID.tolist() == raw.ID.tolist()


REFERENCE = Path(__file__).parent / "fixtures" / "cr_pd_002_reference.py"


def test_a_faithful_translation_reaches_pass_on_all_five_levels(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    shutil.copy(REFERENCE, p)
    cert = parity.run(p, attempt=1, run_id="ref")
    assert cert.overall == "PASS", [(lv.level, lv.value, lv.details) for lv in cert.levels if not lv.passed]


def test_a_naive_translation_fails_at_the_util_cut_points_and_the_localiser_says_so(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text(REFERENCE.read_text().replace('np.searchsorted(CUT_UTIL, f.util.to_numpy(), side="left")', 'np.searchsorted(CUT_UTIL, f.util.to_numpy(), side="right")'))
    cert = parity.run(p, attempt=1, run_id="naive")
    by = {lv.level: lv for lv in cert.levels}
    assert cert.overall == "FAIL" and not by["L1"].passed and not by["L3"].passed and not by["L5"].passed
    assert cert.mismatch_summary["util"]["pattern"] == "all exactly at cut point"
    assert cert.mismatch_summary["util"]["nearest_cut"] in (0.0, 0.25, 0.5, 0.75, 1.0)


def test_parity_refuses_to_execute_code_that_breaks_the_sandbox_rules(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text("import os\nos.environ['PWNED'] = '1'\n")
    cert = parity.run(p, attempt=1, run_id="evil")
    import os

    assert "PWNED" not in os.environ
    assert cert.overall == "FAIL" and "sandbox" in cert.mismatch_summary["error"]


def test_a_label_format_mismatch_reports_the_missing_golden_labels_and_a_count_only(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text(REFERENCE.read_text().replace('format(x, ".15g")', "str(float(x))"))
    l1 = parity.run(p, attempt=1, run_id="labels").levels[0]
    assert not l1.passed and l1.details["extra_bins"] > 0
    ex = l1.details["examples"]
    assert 0 < len(ex) <= 6 and all(e.endswith("|missing in rebuilt") for e in ex)
    assert not any(".0" in ex for ex in l1.details["examples"])  # nothing the module wrote is echoed


def test_failure_details_never_echo_numbers_or_extra_keys_the_module_controls(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text(REFERENCE.read_text()
                 .replace("def fit(dev: pd.DataFrame) -> dict[str, float]:", "def fit(dev: pd.DataFrame) -> dict[str, float]:\n    return {'leak 4711 0.123456': 1.0}\n\n\ndef _old_fit(dev):")
                 .replace("def woe_tables(dev: pd.DataFrame) -> pd.DataFrame:", "def woe_tables(dev: pd.DataFrame) -> pd.DataFrame:\n    if dev.AGE.iloc[0] > 0:\n        raise ValueError(f'row {dev.LIMIT_BAL.iloc[0]} {dev.AGE.iloc[0]}')\n    return _w(dev)\n\n\ndef _w(dev):"))
    cert = parity.run(p, attempt=1, run_id="leak")
    text = json.dumps({"summary": cert.mismatch_summary, "details": [lv.details for lv in cert.levels]})
    assert not any(leak in text for leak in ("4711", "20000", "leak", "0.123456"))
    assert cert.mismatch_summary["error"].startswith("ValueError") and "row" not in cert.mismatch_summary["error"]
    assert cert.levels[1].details["extra_terms"] == 1


def test_labels_written_by_the_module_are_never_echoed(tmp_path):
    p = tmp_path / "cr_pd_002.py"
    p.write_text(REFERENCE.read_text().replace("return pd.concat(out, ignore_index=True)", 'out[0].loc[out[0].index[0], "bin_label"] = "(12,34]"\n    return pd.concat(out, ignore_index=True)'))
    details = parity.run(p, attempt=1, run_id="lab").levels[0].details
    assert details["extra_bins"] > 0 and "12,34" not in json.dumps(details)

@pytest.mark.parametrize(
    ("raises", "expected", "forbidden"),
    [
        ("KeyError('secret_name_xyz')", "KeyError at line", "secret_name_xyz"),
        ("KeyError('woe_util')", "KeyError `woe_util` at line", None),
        ("type('Row1234Leak', (Exception,), {})('x')", "Exception at line", "Row1234Leak"),
        ("type('Row9Spoof', (Exception,), {'__module__': 'builtins'})('x')", "Exception at line", "Row9Spoof"),
        ("type('Row7Sub', (ValueError,), {})('x')", "ValueError at line", "Row7Sub"),
        ("ValueError('row 20000 24')", "ValueError at line", "row"),
    ],
)
def test_only_known_names_and_builtin_or_library_exception_types_are_echoed(tmp_path, raises, expected, forbidden):
    p = tmp_path / "cr_pd_002.py"
    p.write_text(f"def score(df, coefs, woe):\n    raise {raises}\n")
    error = parity.run(p, attempt=1, run_id="names").levels[0].details["error"]
    assert error.startswith(expected) and (forbidden is None or forbidden not in error)
