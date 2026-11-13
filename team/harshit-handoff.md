# WP3 integration handoff

Implemented metrics, fairness, tiering, validation, simulated monitoring, printable HTML reports, reusable charts and optional MLflow tracking. Source and tests are on harshit/validation.

## Integration actions

- TODO(Varun): config.ROOT currently uses Path(__file__).resolve().parents[2], which resolves to repo/src. For src/modelproof/config.py the repository root is parents[3]. This prevents reading repo/config/policy.yaml and points the legacy/rebuilt paths at src. Shared file deliberately left to its owner. WP3 tests isolate ROOT to the repository explicitly.
- TODO(Dhrishit): provide processed CR-PD-002 dev/holdout and the parity.score_fn callable. No stand-in scorer is installed in production source.
- TODO(Varun): agents.validate writes validation_report.json. WP3 run_suite writes validation_results.json only, matching B8. Then call report.render.validation(model_id).
- TODO(Aayush): charts are matplotlib Figures. Fairness output has by_sensitive and flattened groups with worst_dp_ratio, worst_eod and four_fifths_flag. UI should explain that approval is the favourable decision; group TPR is approval among repayers and FPR is approval among defaulters.

## Reproduction in the shared environment

Run uv sync --all-extras, then uv run ruff check . and uv run pytest -q. Tests never download datasets. tests/conftest.py supplies contract-only shared modules only when absent; it uses the real schema/config/audit when present. Synthetic scorers stay in tests.

## Methodology details

Thresholds are loaded from fixed policy. Undefined statistics become unavailable/amber. HL uses the effective number of nonempty probability groups minus two degrees of freedom if ties reduce the number of groups. IV uses half-event smoothing. The suite rejects duplicate/missing scoring IDs and overlapping dev/holdout IDs. Descriptive checks without a policy limit explicitly say so.

Monitoring resamples 3000 loans per month with synthetic unique scoring IDs, preserves observed outcomes, applies the fixed month 4/5/6 shocks and labels all outputs simulated drift. It demonstrates sensitivity to population change, not future credit outcomes.

MLflow is optional. The missing-library path is silent. Live tracking/registry needs an installed server/client and the verified WP2 scorer; it has not been exercised against a live service here.

## Remaining team deliverables

The real-data run, integration merge and Part D slides need the other contributors' modules and artifacts/metrics.json. Do not invent cost, benchmark numbers, screenshots or a passing real model result. No submission email or deployment is performed by WP3.

## Verified checks

All 57 tests passed on Python 3.12 using scipy 1.15.3, scikit-learn 1.6.1, fairlearn 0.12.0, matplotlib 3.10.3, pandas 2.2.3 and numpy 2.2.6. Ruff and syntax compilation also pass. Tests cover the real WP1 schema/config/audit plus test-only WP2 data stand-ins. Python 3.11 and the team uv.lock environment still need CI confirmation. Live MLflow and the real rebuilt model remain integration checks.

