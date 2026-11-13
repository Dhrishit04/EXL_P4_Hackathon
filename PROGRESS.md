# PROGRESS (WP1, Varun)

Updated as work lands. Times are Irish time, 13 Nov 2026.

## Done
* 17:40 Scaffold, contract (B1 to B11), config, schemas, audit, policy on `main`; tests green.
* 17:50 `llm.py` (record/replay, usage log, row-data and untrusted-source guards), `inventory.py`.
* 17:55 Agents discover, document, verify, validate; LangGraph gates, CLI; WP3 (harshit/validation) reviewed and merged.
* 18:05 `scripts/benchmark.py`, `replay_check.py`, `run_pipeline.sh`; README draft.

## Waiting on
* WP2 (Dhrishit): data, legacy estate, goldens, extractors, security, sandbox, parity, Redevelop agent, `eval/gold` in the B11 formats.
* WP4 (Aayush): UI, `docs/architecture.mmd`, `docs/AI_TOOLS.md`, CI, live app link.

## Next
Merge WP2 and WP4 as they land, run `scripts/run_pipeline.sh` at 21:15, commit `artifacts/` and `.cache/llm/`, fill README links.
