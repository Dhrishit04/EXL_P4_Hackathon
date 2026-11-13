# PROMPT FOR HARSHIT: WP3 Validation engine and reports (Codex, ChatGPT Plus)

You are Codex working for **Harshit**, one of **4 contributors** building **ModelProof** in parallel for the EXL x UCD hackathon (Challenge 04). The other three are Varun (Claude Code, WP1 core, agents, LangGraph and integration; he merges PRs), Dhrishit (Claude Code, WP2 legacy estate, R goldens, parity and the Redevelop agent) and Aayush (GitHub Copilot, WP4 UI, docs and deploy). Part A says who does what. Part B is the shared contract every contributor codes against.

**Your work package: WP3 Validation engine and reports.** You own every deterministic number the judges will see: performance, calibration, stability, fairness, benchmarking, sensitivity, monitoring, plus the printable HTML reports. This is pure, well specified Python, which suits Codex.

How to start: save this file as `team/harshit.md` and create `AGENTS.md` at the repo root containing one line: "Follow team/harshit.md and CONTRACT.md. Only edit WP3 files." Then start Codex in the repo and say: "Read team/harshit.md and execute Part C in order."

## How to work fast with multiple agents (Codex with ChatGPT Plus)
* Run **Codex CLI** (`codex`) locally on branch `harshit/validation` for work that needs the data.
* In parallel, launch **up to 3 Codex cloud tasks** from ChatGPT (connect GitHub, choose this repo). Each task works on disjoint files and opens its own PR:
  * Task A: `metrics.py`, `fairness.py`, `tiering.py` and their tests.
  * Task B: `report/charts.py`, `report/render.py`, `report/templates/*.html.j2`, built against fixture JSON that follows B6.
  * Task C: `validation.py` and `monitoring.py` with tests on synthetic fixtures.
* Codex cloud tasks usually run without internet, so tests must never download data. Use small synthetic fixtures made in `tests/conftest.py` (seeded logistic data with SEX, MARRIAGE, EDUCATION, AGE columns).
* Review every diff before merging it into your branch. `ruff check --fix .` and `pytest -q` must pass.

---

# PART A. TEAM, TIMELINE AND RULES (identical in all 4 prompts)

## The project in 5 lines
* **ModelProof**: an agentic model risk factory for EXL x UCD Data & AI Hackathon 2026, Challenge 04 (Tier 1 UK bank, about 250 models in SAS, R and Python, PRA SS1/23, 8 to 12 weeks per validation).
* Must show: inventory records and documentation for 3 to 5 models, AI agents rebuilding one SAS or R model in Python with parity proof, an auto generated validation report on performance, stability and fairness, humans reviewing at each gate.
* Design rule: **"LLMs propose, deterministic code disposes."** No number, risk tier or RAG status ever comes from the LLM.
* Differentiators: (1) evidence linked documentation with a claim verifier and doc vs code drift detection, (2) a five level parity certificate from a self healing R to Python translation, (3) governance by construction: human gates, hash chained audit log, LLM never sees row level data, sandboxed generated code, prompt injection scanner, deterministic tiers.
* Judging: Business impact 30%, Technical 25%, Innovation 20%, Responsible AI 15%, Presentation 10%. **Deadline: 13 Nov 2026, 23:59 Irish time.**

Repo: https://github.com/Dhrishit04/EXL_P4_Hackathon (owner: Dhrishit). Full single builder spec, for reference only: `docs/SPEC.md` once Varun pushes it. Where it differs from your work package, your work package wins.

## The 4 contributors (everyone works in parallel on separate files)

| Contributor | AI tool | Work package | Branch |
| --- | --- | --- | --- |
| Varun | Claude Code (Claude Pro) | **WP1 Core and integration**: scaffold, shared contract files (schemas, config, policy, audit), LLM layer with record/replay, Discover, Document, Verify and Validate agents, LangGraph human gates, CLI, end to end run, benchmark, README. Merges all PRs. | `varun/core` |
| Dhrishit | Claude Code (Claude Pro) | **WP2 Legacy estate and rebuild**: data download and splits, the simulated legacy estate (4 SAS, R, Python models with seeded issues), R golden outputs, ground truth, code fact extractors, injection scanner, sandbox, five level parity harness and certificate, Redevelop agent. | `dhrishit/legacy-parity` |
| Harshit | Codex (ChatGPT Plus) | **WP3 Validation engine and reports**: metrics, fairness, tiering, validation suite with RAG, monitoring simulation, charts, HTML reports, MLflow tracking. | `harshit/validation` |
| Aayush | GitHub Copilot | **WP4 UI, docs and deploy**: Streamlit validator workbench, Streamlit Cloud deployment, architecture diagram source, Responsible AI note, AI tools declaration, demo script, CI. | `aayush/ui-docs` |

## Rules for everyone
1. **Only edit files your work package owns** (see the layout in Part B). Need a change in someone else's file? Message them, or write `TODO(<owner>): ...` in your PR description. Never reformat other people's files.
2. Shared files owned by Varun: `pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example`, `config/policy.yaml`, `CONTRACT.md`, `src/modelproof/{__init__,config,schemas,audit,llm}.py`. Every dependency is already listed in Part B. Do not add packages without asking Varun.
3. Code against **Part B exactly**: names, signatures, file paths and JSON shapes. If a module you depend on is not on `main` yet, put a tiny stub in your **tests only**, never in `src/`.
4. Git: branch from `main`, commit small and often, `git pull --rebase origin main` before every push, open a PR into `main` early and keep pushing to it. Varun merges.
5. **Never invent results.** Every number in the UI, docs, README or slides must come from a file the code produced. Anything simulated (monitoring drift) or seeded (planted document errors, planted injection) is labelled "simulated" or "seeded" wherever it appears.
6. Efficiency is judged: smallest correct code, functions over classes, vectorised pandas and numpy, type hints, `random_state=42` / seed 42 everywhere, `ruff check --fix` clean, the whole `pytest -q` under 60 s.
7. **Use several AI agents in parallel** (your tool section explains how) to go faster, but review and test everything they produce. Give each agent disjoint files so they never edit the same file.
8. Secrets: `.env` is never committed. Varun shares the runtime LLM key privately.
9. If your AI tool hits its usage limit: commit, push, write where you stopped in your PR description, and tell the team at once so someone else can continue.

## Timeline (Irish time, today)

| Time | Milestone |
| --- | --- |
| 17:30 | Everyone starts. Dhrishit adds the other three as repo collaborators first. |
| by 17:55 | Varun pushes scaffold + contract files to `main`. Everyone else rebases onto it. |
| 19:30 | **Checkpoint 1** PRs merged: WP2 data, legacy estate, goldens, extractors, parity; WP3 metrics, fairness, tiering, validation suite; WP4 UI skeleton on fixtures; WP1 llm.py and agents. |
| 20:45 | **Checkpoint 2** PRs merged: WP2 Redevelop agent; WP3 monitoring and reports; WP4 full UI and docs; WP1 graph and CLI. |
| 21:15 | Varun runs the full pipeline live, then in replay mode, and commits artifacts and the replay cache. Everyone fixes bugs in their own files. |
| 21:45 | **Code freeze.** Benchmark writes `artifacts/metrics.json`. Aayush deploys Streamlit Cloud. |
| 21:45 to 23:20 | Submission pack: deck (Aayush with Harshit), demo video (Dhrishit), README and links (Varun). |
| 23:30 | Email sent from a UCD address to Monika.Rawal@exlservice.com, subject `EXL Hackathon | <Team name> | Challenge 04`. |

---

# PART B. THE CONTRACT (identical in all 4 prompts; Varun commits it as CONTRACT.md)

## B1. Repository layout and ownership

```
EXL_P4_Hackathon/
  README.md, CONTRACT.md, pyproject.toml, uv.lock, .gitignore, .env.example     WP1
  requirements.txt                       WP4 (UI only, for Streamlit Cloud)
  config/policy.yaml                     WP1 (content fixed in B3)
  prompts/discover.md document.md validate.md   WP1
  prompts/redevelop.md                   WP2
  scripts/fetch_data.py                  WP2
  scripts/benchmark.py                   WP1
  data/raw/ (gitignored)  data/processed/  data/DATA_CARD.md    WP2
  legacy_estate/<model folder>/...       WP2
  eval/gold/                             WP2 (agents and prompts must NEVER read this)
  src/modelproof/
    __init__.py config.py schemas.py audit.py llm.py graph.py cli.py   WP1
    agents/__init__.py discover.py document.py verify.py validate.py     WP1
    agents/redevelop.py                                                  WP2
    data.py security.py sandbox.py parity.py                             WP2
    extract/__init__.py sas.py r.py py.py                                WP2
    metrics.py fairness.py tiering.py validation.py monitoring.py tracking.py   WP3
    report/__init__.py charts.py render.py templates/*.html.j2           WP3
  rebuilt/                    generated by the Redevelop agent (never hand written)
  artifacts/                  generated outputs, committed for demo mode
  app/Home.py app/pages/*.py .streamlit/config.toml     WP4
  docs/SPEC.md                WP1
  docs/*.md docs/architecture.mmd                       WP4
  tests/test_<module>.py      owner of that module
  tests/fixtures/             WP3 (metric fixtures), WP4 (UI fixtures)
  .github/workflows/ci.yml    WP4
  team/<name>.md              each person's own prompt file
```

Model ids and folders (constant `MODELS` in `config.py`):

| model_id | folder | language | data | role |
| --- | --- | --- | --- | --- |
| CR-PD-001 | `legacy_estate/CR-PD-001_sas_application_scorecard` | SAS | German Credit | documented; seeded `personal_status` proxy |
| CR-PD-002 | `legacy_estate/CR-PD-002_r_card_default_pd` | R | Taiwan defaults | **rebuild target**, full validation and monitoring |
| FR-TX-003 | `legacy_estate/FR-TX-003_py_card_fraud` | Python | synthetic transactions | undocumented model |
| PR-RB-004 | `legacy_estate/PR-RB-004_sas_risk_based_pricing` | SAS | German Credit | seeded prompt injection; depends on CR-PD-001 |

## B2. Dependencies (all in pyproject from the start)
Python 3.11. Core: pandas, numpy, scipy, statsmodels, scikit-learn, fairlearn, pydantic>=2, pyyaml, jinja2, matplotlib, typer, python-dotenv, ucimlrepo, langgraph, langgraph-checkpoint-sqlite, langchain. Extras: `anthropic` (langchain-anthropic), `openai` (langchain-openai, also Azure OpenAI and OpenAI compatible endpoints), `google` (langchain-google-genai), `tracking` (mlflow), `ui` (streamlit), `dev` (pytest, ruff). Package manager: `uv` (`uv sync --all-extras`). Legacy runtime: base R (`Rscript`), no CRAN packages.

## B3. config/policy.yaml (fixed before any run; never tune after seeing results)
```yaml
seed: 42
psi: {green: 0.10, amber: 0.25}            # < green stable; < amber investigate; else red (Lewis/Siddiqi)
csi: {green: 0.10, amber: 0.25}
gini: {green: 0.40, amber: 0.30}           # >= green, >= amber, else red (team policy)
gini_drop_rel: {green: 0.05, amber: 0.10}  # dev to holdout relative drop
hosmer_lemeshow_p: {green: 0.05}
jeffreys: {alpha: 0.05, amber_failures: 1, red_failures: 2}   # ECB style one sided test per grade
fairness: {dp_ratio_green: 0.80, dp_ratio_amber: 0.70, eod_green: 0.10, eod_amber: 0.20}   # four fifths rule
vif: {green: 5, amber: 10}
iv_useless: 0.02
benchmark_gini_gap: {green: 0.05, amber: 0.10}      # challenger Gini minus model Gini
sensitivity_mean_shift: {green: 10, amber: 20}      # mean score points moved by a 10% shock
missing_rate: {green: 0.01, amber: 0.05}
parity: {coef_load_abs: 1.0e-12, coef_refit_abs: 1.0e-6, pd_abs: 1.0e-9}
tier_matrix: {HH: 1, HM: 1, MH: 1, HL: 2, MM: 2, LH: 2, ML: 3, LM: 3, LL: 3}   # materiality+complexity
validation_months_by_tier: {1: 12, 2: 24, 3: 36}
monitoring_triggers: {score_psi: 0.25, gini_drop_rel: 0.10, jeffreys_failures: 1}
rating_rule: {not_fit_if_red_at_least: 2, conditions_if_red_or_amber_at_least: 1}
llm_prices_per_mtok: {input: 3.0, output: 15.0}   # edit to your provider's prices
max_redevelop_attempts: 4
```

## B4. Data contract (WP2 produces, everyone reads through `modelproof.data`)
* `data/processed/cr_pd_002_dev.csv`, `cr_pd_002_holdout.csv` (Taiwan, stratified 70/30, seed 42), `cr_pd_002_edge.csv` (rows built to land exactly on every cut point). Columns: `ID, LIMIT_BAL, SEX, EDUCATION, MARRIAGE, AGE, PAY_0, PAY_2, PAY_3, PAY_4, PAY_5, PAY_6, BILL_AMT1..BILL_AMT6, PAY_AMT1..PAY_AMT6, DEFAULT` (edge rows have DEFAULT 0 and are never used for metrics).
* `data/processed/german_credit.csv` (OpenML credit-g columns + `ID` + `bad` 0/1). `data/processed/fraud_transactions.csv` (synthetic: `ID, amount, hour, merchant_cat, card_present, country_mismatch, txn_velocity_24h, account_age_days, is_fraud`).
* `modelproof.data`: `load_cr_pd_002(split: Literal["dev","holdout","edge"]) -> pd.DataFrame`, `load_german() -> pd.DataFrame`, `load_fraud() -> pd.DataFrame`, `age_band(age: pd.Series) -> pd.Series` (labels `<25, 25-34, 35-44, 45-54, 55+`), `PROTECTED = ["SEX", "MARRIAGE", "AGE_BAND", "EDUCATION"]`.
* R golden outputs in `legacy_estate/CR-PD-002_r_card_default_pd/golden/`: `coefficients.csv (term, estimate)`, `woe_tables.csv (feature, bin_label, lower, upper, closed, n, n_bad, woe)`, `scored_dev.csv`, `scored_holdout.csv`, `scored_edge.csv` (all `ID, pd, score, grade, decision`), `r_session.txt`. Numbers written with `sprintf("%.17g")`.

## B5. Rebuilt model contract (`rebuilt/cr_pd_002.py`, written by the Redevelop agent only)
`build_features(df) -> DataFrame`, `apply_bins(features) -> DataFrame` (bin labels equal to golden `bin_label`), `woe_tables(dev_df) -> DataFrame` (same columns as golden), `fit(dev_df) -> dict[str, float]` (statsmodels GLM Binomial), `score(df, coefs: dict[str, float], woe: DataFrame) -> DataFrame` (`ID, pd, score, grade, decision`). WP2 exposes `parity.score_fn(module_path) -> Callable[[DataFrame], DataFrame]` that scores raw rows with the golden coefficients and WoE tables; WP1 and WP3 use only this callable.

## B6. Schemas (`src/modelproof/schemas.py`, Pydantic v2, owned by WP1, exact)
```python
Level = Literal["H", "M", "L"]; RAG = Literal["green", "amber", "red"]
class Evidence(BaseModel): id: str; kind: Literal["code","doc","metric","data"]; path: str; line_start: int; line_end: int; excerpt: str; sha256: str = ""
class Facts(BaseModel): model_id: str; language: Literal["SAS","R","Python"]; files: list[dict]  # {path, sha256, n_lines, kind: "code"|"doc"}
    datasets_read: list[str] = []; datasets_written: list[str] = []; variables_created: list[str] = []; variables_used: list[str] = []
    dead_variables: list[str] = []; model_calls: list[dict] = []  # {kind, text, evidence_id}
    target: str | None = None; parameters: dict[str, dict] = {}  # name -> {value, evidence_id}
    dependencies: list[str] = []; evidence: list[Evidence] = []
class Feature(BaseModel): name: str; transformation: str = ""; evidence_id: str | None = None
class Drift(BaseModel): field: str; doc_value: str; code_value: str; doc_evidence_id: str; code_evidence_id: str; verified: bool = False
class Finding(BaseModel): id: str; model_id: str; area: str; severity: Literal["high","medium","low"]; ss123_principle: Literal["P1","P2","P3","P4","P5"]
    description: str; evidence_ids: list[str] = []; recommendation: str = ""; status: Literal["open","closed"] = "open"
class Approval(BaseModel): gate: Literal["discovery","documentation","redevelopment","validation","override"]; decision: Literal["approve","reject"]
    reviewer: str; comment: str = ""; ts: datetime; auto: bool = False
class InventoryRecord(BaseModel): model_id: str; name: str; version: str = "1.0"; purpose: str = ""; business_use: str = ""; portfolio: str = ""
    model_type: Literal["PD","LGD","fraud","pricing","other"]; methodology: str = ""; platform_language: str; source_files: list[dict] = []
    input_data: list[str] = []; features: list[Feature] = []; target_definition: str = ""; outputs: list[str] = []
    upstream_models: list[str] = []; downstream_models: list[str] = []; owner_role: str = ""; developer_role: str = ""; validator_role: str = ""
    materiality: Level; materiality_rationale: str = ""; complexity: Level; complexity_rationale: str = ""; risk_tier: int
    ai_ml_flag: bool = False; regulatory_use: str = ""; documentation_status: Literal["current","outdated","missing"]
    doc_code_drifts: list[Drift] = []; security_flags: list[Finding] = []; last_validated: date | None = None; next_validation_due: date | None = None
    monitoring_kpis: list[str] = []; limitations: list[str] = []
    status: Literal["discovered","documented","redeveloped","validated","monitored","revalidation_required"] = "discovered"; approvals: list[Approval] = []
class Claim(BaseModel): section: str; text: str; evidence_ids: list[str] = []; status: Literal["supported","unsupported","contradicted"] = "unsupported"; reason: str = ""
class Documentation(BaseModel): model_id: str; claims: list[Claim]; grounding_score: float; drifts: list[Drift] = []; generated_at: datetime
class ParityLevel(BaseModel): level: Literal["L1","L2","L3","L4","L5"]; name: str; passed: bool; metric: str; value: float; tolerance: float; details: dict = {}
class ParityCertificate(BaseModel): model_id: str; overall: Literal["PASS","FAIL"]; levels: list[ParityLevel]; hashes: dict[str, str]; versions: dict[str, str]
    mismatch_summary: dict = {}; attempt: int; run_id: str; created_at: datetime
class CheckResult(BaseModel): test: str; area: Literal["discrimination","calibration","stability","conceptual","benchmark","sensitivity","fairness","data_quality","implementation"]
    value: float | None; threshold: str; rag: RAG; ss123_principle: str = "P4"; details: dict = {}
class ValidationResults(BaseModel): model_id: str; tests: list[CheckResult]; tables: dict[str, list[dict]] = {}; charts: dict[str, dict] = {}
class ValidationReport(BaseModel): model_id: str; results: ValidationResults; narrative: dict[str, str]; findings: list[Finding]
    rating: Literal["Fit for use","Fit with conditions","Not fit"]; claims: list[Claim] = []; created_at: datetime
class MonitoringPoint(BaseModel): month: int; score_psi: float; csi: dict[str, float]; gini: float; observed_dr: float; expected_dr: float; jeffreys_failures: int; breaches: list[str] = []
class MonitoringResult(BaseModel): model_id: str; points: list[MonitoringPoint]; trigger_month: int | None; simulated: bool = True
```

## B7. Function signatures by module
* **config (WP1)**: `ROOT, DATA_RAW, DATA_PROCESSED, LEGACY, GOLD_DIR, ARTIFACTS (env MODELPROOF_ARTIFACTS, default ROOT/artifacts), REBUILT, CACHE (.cache/llm)`, `MODELS: dict[str, str]`, `REBUILD_TARGET = "CR-PD-002"`, `load_policy() -> dict`, `artifact_dir(model_id) -> Path` (creates it).
* **audit (WP1)**: `append(event: str, payload: dict, model_id: str | None = None, actor: str = "system") -> str`, `read() -> list[dict]`, `verify_chain() -> bool`. File `artifacts/audit/audit_log.jsonl`, entry `{ts, actor, event, model_id, payload, prev_hash, hash}`, `hash = sha256(prev_hash + canonical_json(entry_without_hash))`.
* **llm (WP1)**: `structured(system: str, user: str, schema: type[BaseModel], task: str) -> BaseModel`, `text(system: str, user: str, task: str) -> str`, `untrusted(path: str, content: str) -> str` (wraps source in `<untrusted_source path="...">` tags), `assert_no_row_data(text: str) -> None`.
* **agents (WP1)**: `discover.run(model_id) -> InventoryRecord`, `document.run(model_id) -> Documentation`, `verify.verify(claims, facts, metrics: dict | None = None) -> tuple[list[Claim], float]`, `validate.run(model_id) -> ValidationReport`.
* **graph (WP1)**: `run(model_id, auto_approve: bool = False) -> dict`, `pending_gates() -> list[dict]` (`thread_id, model_id, gate, summary, artifacts`), `resume(thread_id: str, decision: str, comment: str, reviewer: str) -> dict`.
* **data (WP2)**: see B4.
* **extract (WP2)**: `facts_for(model_id) -> Facts` (also writes `artifacts/<id>/facts.json`).
* **security (WP2)**: `scan(model_id) -> list[Finding]`.
* **sandbox (WP2)**: `check_code(code: str) -> list[str]` (violations, empty means OK), `run_pytest(workdir: Path, timeout: int = 120) -> tuple[bool, str]`.
* **parity (WP2)**: `run(module_path: Path, attempt: int, run_id: str) -> ParityCertificate`, `score_fn(module_path: Path) -> Callable[[DataFrame], DataFrame]`.
* **agents.redevelop (WP2)**: `run(model_id: str = "CR-PD-002", max_attempts: int | None = None, reviewer_comment: str = "") -> ParityCertificate`.
* **metrics (WP3)**: `auc, gini, ks, brier (y, p) -> float`, `bootstrap_ci(fn, y, p, n=500, seed=42) -> tuple[float, float]`, `hosmer_lemeshow(y, p, groups=10) -> tuple[float, float]`, `calibration_table(y, p, bins=10) -> DataFrame`, `jeffreys_by_grade(df, grade="grade", pd_col="pd", y="DEFAULT", alpha=0.05) -> DataFrame`, `psi(expected, actual, bins=10) -> float`, `csi(ref: DataFrame, cur: DataFrame, cols) -> dict[str, float]`, `woe_iv(binned: Series, y: Series) -> tuple[DataFrame, float]`, `vif(df) -> dict[str, float]`, `hhi(labels: Series) -> float`.
* **fairness (WP3)**: `report(df, y: str, approved: str, score: str, sensitive: list[str]) -> dict`.
* **tiering (WP3)**: `assign(materiality: str, complexity: str) -> int`, `next_due(tier: int, last_validated: date | None) -> date`.
* **validation (WP3)**: `run_suite(model_id, dev: DataFrame, holdout: DataFrame, score_fn, features: list[str]) -> ValidationResults` (writes `validation_results.json`), `rating(tests: list[CheckResult]) -> str`.
* **monitoring (WP3)**: `simulate(model_id, holdout: DataFrame, score_fn, months: int = 6) -> MonitoringResult` (writes `monitoring.json`).
* **report (WP3)**: `charts.*(...) -> matplotlib Figure`, `charts.to_base64(fig) -> str`, `render.documentation(model_id)`, `render.parity(model_id)`, `render.validation(model_id)`, `render.inventory()`, each returns the HTML `Path`.
* **tracking (WP3)**: `log(model_id) -> None` (silent no-op if mlflow is not installed).

## B8. Artifacts (all under `artifacts/`; the UI reads only these)
| File | Schema | Writer |
| --- | --- | --- |
| `inventory/inventory.json`, `inventory/inventory.csv`, `inventory/inventory.html` | `list[InventoryRecord]` | WP1 (html by WP3) |
| `<id>/facts.json` | `Facts` | WP2 |
| `<id>/documentation.json`, `<id>/documentation.html` | `Documentation` | WP1 (html WP3) |
| `CR-PD-002/redevelop/attempt_<n>/` `cr_pd_002.py`, `test_cr_pd_002.py`, `certificate.json`, `test_output.txt` | | WP2 |
| `<id>/parity_certificate.json`, `.html` | `ParityCertificate` | WP2 (html WP3) |
| `<id>/validation_results.json` | `ValidationResults` | WP3 |
| `<id>/validation_report.json`, `.html` | `ValidationReport` | WP1 (html WP3) |
| `<id>/monitoring.json`, `<id>/monitoring.png` | `MonitoringResult` | WP3 |
| `audit/audit_log.jsonl` | audit entry | everyone via `audit.append` |
| `runs/<run_id>/llm_usage.jsonl` | `{ts, task, provider, model, input_tokens, output_tokens, cost_usd, cache_hit}` | WP1 |
| `checkpoints.sqlite` | LangGraph | WP1 |
| `metrics.json` | benchmark keys | WP1 |

## B9. CLI and environment
CLI `modelproof` (typer, WP1): `discover`, `run --model ID [--auto-approve]`, `approve --thread T --decision approve|reject --comment C`, `status`, `monitor --model ID --months 6`, `benchmark`, `verify-audit`.
`.env`: `LLM_PROVIDER` (anthropic | openai | azure_openai | google_genai), `LLM_MODEL`, `LLM_MODE` (auto | live | record | replay), provider keys, `OPENAI_BASE_URL` (OpenAI compatible endpoints), `MLFLOW_TRACKING_URI=sqlite:///mlflow.db`, `RSCRIPT=Rscript`, `MODELPROOF_ARTIFACTS=artifacts`.

---

# PART C. YOUR TASKS (WP3, in order)

### C0. Setup (5 min)
Accept Dhrishit's collaborator invite. Install `uv`. Create branch `harshit/validation`. Start C1 straight away; rebase onto `main` when Varun's scaffold lands (about 17:55), then import schemas from `modelproof.schemas` and thresholds from `config.load_policy()`. Until Dhrishit's processed data is on `main`, develop locally against `fairlearn.datasets.fetch_credit_card()` with a quick sklearn logistic regression as a stand in `score_fn`. Keep that stand in **in tests or a local scratch script only, never in `src/`**.

### C1. `metrics.py` (pure functions, numpy and scipy, vectorised)
* `auc` (rank based or sklearn), `gini = 2*auc - 1`, `ks` (max distance between the good and bad score CDFs), `brier`.
* `bootstrap_ci`: 500 resamples drawn as one index matrix with `np.random.default_rng(42)`; returns the 2.5 and 97.5 percentiles.
* `hosmer_lemeshow`: deciles of p; chi square statistic; p value with `groups - 2` degrees of freedom.
* `calibration_table`: per decile count, mean predicted, observed rate.
* `jeffreys_by_grade`: per grade N, D, mean PD, `p = scipy.stats.beta.cdf(mean_pd, D + 0.5, N - D + 0.5)`, `fail = p < alpha` (one sided: the PD is too low).
* `psi`: bins are quantiles of `expected` (10 by default), the same edges are applied to `actual`, epsilon 1e-6, `sum((a - e) * ln(a / e))`. `csi`: PSI per column.
* `woe_iv`, `vif` (with numpy lstsq, no extra dependency), `hhi`.
* Tests with known answers: a perfect ranking gives AUC 1; identical distributions give PSI 0; a hand computed Jeffreys example; a hand computed HL example; VIF of independent columns is about 1.

### C2. `fairness.py` and `tiering.py`
* `fairness.report(df, y, approved, score, sensitive)`: fairlearn `MetricFrame` per sensitive column for approval rate, TPR, FPR and AUC per group, plus `demographic_parity_ratio` and `equalized_odds_difference`. Return a dict with per group tables (records), the worst ratio and difference, and a four fifths flag.
* `tiering.assign` uses `policy.tier_matrix` (key = materiality + complexity, for example `HM`). `tiering.next_due` adds `validation_months_by_tier[tier]` months to `last_validated`, or to today if it is None.

### C3. `validation.py`, PR by checkpoint 1 at 19:30
`run_suite(model_id, dev, holdout, score_fn, features)` scores dev and holdout with `score_fn`, joins on `ID`, adds `AGE_BAND` via `data.age_band`, then produces `CheckResult`s with RAG from the policy:
* **Discrimination (P4):** Gini on dev and holdout with bootstrap CIs, KS and AUC on holdout, relative Gini drop from dev to holdout.
* **Calibration (P4):** HL p value on holdout, Brier score, calibration table, number of Jeffreys failures across grades.
* **Stability (P4):** score PSI from dev to holdout; CSI per raw feature.
* **Conceptual soundness (P3):** IV per raw feature (decile bins), flagging IV below `iv_useless`; VIF across numeric raw features; share of grades by HHI.
* **Benchmark (P4):** a challenger `HistGradientBoostingClassifier` (seed 42) trained on dev raw features and scored on holdout. Gap = challenger Gini minus model Gini, RAG from `benchmark_gini_gap`.
* **Sensitivity (P4):** shock `BILL_AMT1` and `LIMIT_BAL` up and down 10%, rescore, report the mean absolute score shift against `sensitivity_mean_shift`.
* **Fairness (P4):** `approved = decision == "approve"`, sensitive columns from `data.PROTECTED`, worst demographic parity ratio and worst equalized odds difference across them.
* **Data quality (P3):** missing rate per column against `missing_rate`, plus range checks (AGE 21 to 79, SEX in {1, 2}).
* **Implementation (P3):** read `artifacts/<id>/parity_certificate.json` if present; green if PASS, red if FAIL, amber if missing.
* `tables`: calibration, Jeffreys, fairness by group, CSI, IV. `charts`: ROC points, KS curves, score histograms for dev and holdout, calibration points. Store them as plain lists so the UI can redraw them.
* `rating(tests)`: per `policy.rating_rule`: "Not fit" if reds >= 2; "Fit with conditions" if at least 1 red or amber; else "Fit for use".
* Write `artifacts/<id>/validation_results.json`. Call `audit.append("validation_suite_run", {...})`.
* Tests on the synthetic fixture: every area produces at least one result, every RAG matches the thresholds, the JSON round trips through `ValidationResults`.

### C4. `monitoring.py`, PR by checkpoint 2 at 20:45
`simulate(model_id, holdout, score_fn, months=6)`: each month samples 3,000 holdout rows with replacement (seed 42 + month). Months 1 to 3 are unchanged. Months 4 to 6 add progressive, documented stress: multiply `BILL_AMT1` by 1.15, 1.30 and 1.50, and add 1 to `PAY_0` for 10%, 20% and 30% of rows. Labels stay as observed (state this limitation). Per month compute score PSI against the scores of the full holdout (the reference), CSI of the stressed features, Gini, observed vs expected default rate, Jeffreys failures, and breaches against `monitoring_triggers`. `trigger_month` is the first month with a breach. Write `monitoring.json` and `monitoring.png` (PSI by month with the 0.10 and 0.25 lines and the trigger marked). Label everything "simulated drift".

### C5. Reports (`report/charts.py`, `report/render.py`, `report/templates/`), PR by checkpoint 2
* `charts.py`: matplotlib functions taking plain data and returning a `Figure`: ROC, KS, calibration by decile, score distribution dev vs holdout, PSI by month, fairness bars by group, RAG summary. `to_base64(fig)` for HTML embedding. Navy and orange accents plus RAG colours, readable fonts, no chart junk. Aayush's UI reuses these through `st.pyplot`.
* `render.py` with Jinja2 templates and an A4 print stylesheet (clean, professional, one shared base template):
  * `documentation.html`: grounding score badge, one section per template heading, each claim with footnoted evidence (file:line and a code excerpt), unsupported claims highlighted amber, and a drift table (doc line vs code line).
  * `parity_certificate.html`: five levels with tolerance, value and pass/fail, hashes, versions, a large PASS/FAIL stamp and the attempt history (read the attempt folders).
  * `validation_report.html`: executive summary, overall rating, RAG table grouped by area with SS1/23 principle, charts, findings with severity and recommendation, and a sign off block filled from audit log approvals (show "auto (demo flag)" honestly).
  * `inventory.html`: one row per model with tier, status, documentation status, drift count and security flags.
* Each function reads the JSON artifacts from B8 and writes the HTML next to them. Develop against fixture JSON in `tests/fixtures/` that follows B6.

### C6. `tracking.py`
`log(model_id)`: if `mlflow` imports, set the tracking URI from env, log coefficients as params, the validation metrics, and the certificate and report as artifacts, then register `CR-PD-002-python` with tags (tier, parity status, rating). Otherwise do nothing silently. One sentence in the docstring: Azure ML works by pointing `MLFLOW_TRACKING_URI` at the workspace and installing `azureml-mlflow`.

### Definition of done for WP3
Metrics, fairness, tiering and validation merged by 19:30. Monitoring, reports and tracking merged by 20:45. On Varun's full run the reports render with real numbers, and every RAG traces back to `policy.yaml`.

# PART D. YOUR NON CODE TASKS AFTER 21:45
With Aayush, build the deck. You own template page 4 (technologies, estimated cost from `metrics.json`) and page 5 (three screenshots plus the three headline numbers from `metrics.json`), plus two extra slides: the validation report RAG table with key charts, and the monitoring drift timeline. Every number comes from `artifacts/`.
