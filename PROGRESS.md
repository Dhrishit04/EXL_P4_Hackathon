# PROGRESS (WP1, Varun)

Times are Irish time, 13 Nov 2026. `main` is always green: `uv run pytest -q` and `uv run ruff check .`.

## Done and on `main`
* Scaffold, `CONTRACT.md` (B1 to B11), `config`, `schemas` (exact B6), `audit` (hash chain), `config/policy.yaml` (exact B3).
* `llm.py`: LangChain provider-agnostic, record/replay cache (`auto|live|record|replay`), usage log with cost, row-data guard, untrusted-source wrapper and guard sentence, repair retry, transient retries.
* `inventory.py`; agents `discover`, `document`, `verify`, `validate` with prompts; `graph.py` (LangGraph, SQLite checkpoints, human gates, auto-approve recorded as `auto`, revalidation loop once, per-stage timings); `cli.py` (all B9 commands).
* `scripts/benchmark.py` (metrics.json + README results table), `scripts/replay_check.py`, `scripts/run_pipeline.sh`.
* Reviewed and merged WP3 (`harshit/validation`) and WP2 part 1 (`dhrishit/legacy-parity`: data, legacy estate, goldens, gold files, extractors, scanner).
* Integration tests with the real extractors, scanner, tiering and renderers (only the LLM is scripted).

## Not done yet
* **C0 runtime LLM key**: none configured on this machine. Nothing has been run against a real LLM, so the prompts are untested live.
* WP2 still to land: `parity.py`, `sandbox.py`, `agents/redevelop.py`, `prompts/redevelop.md`. The graph's `redevelop`, `validate` and `monitor` stages need them.
* WP4 still to land: UI, `docs/architecture.mmd`, CI, live app link.
* C5 live run and replay run, then commit `artifacts/` and `.cache/llm/`: `scripts/run_pipeline.sh` (needs the key and the items above).
* README: Mermaid diagram, results table (generated), app and video links.
* Part D: README links, no secrets in git, confirm who sends the email.
