# PROGRESS

Times are Irish time, 13 Nov 2026.

## In the repository
* Core: contract, config, schemas, hash-chained audit log, LLM layer (record/replay, usage log, row-data and untrusted-source guards), agents discover/document/verify/validate, LangGraph human gates, CLI, benchmark, replay check, pipeline runner.
* Legacy estate, data, R golden outputs, ground truth, fact extractors, injection and proxy scanner, sandbox, five-level parity harness, Redevelop agent.
* Validation suite, fairness, tiering, monitoring simulation, reports, optional MLflow tracking.
* Streamlit validator workbench (shows a FIXTURE DATA banner until real artifacts exist), docs, CI.

## Not done yet
* Nothing has been run against a live LLM: no `rebuilt/cr_pd_002.py`, no committed `artifacts/` or `.cache/llm/`, no `artifacts/metrics.json`, so the README results table is empty.
* A runtime LLM key and model id in `.env` (`LLM_MODEL` has no default).
* README: live app link and demo video link.
* `docs/RESPONSIBLE_AI.md` has dataset licence items marked TODO.
