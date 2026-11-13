# ModelProof presentation content

Ten-slide copy outline. Replace numeric metric placeholders only with values
verified from a real run. No real run `metrics.json` or screenshots are
available in this repository; keep placeholders until those artifacts are
provided. Bracketed team, cost, and link fields also need confirmation.

## Slide 1 — ModelProof: validation with evidence

**On slide**

- **Event:** EXL x UCD Data & AI Hackathon, Challenge 04
- **Team:** [Team name to confirm]
- **Challenge:** Make legacy bank-model validation more traceable, repeatable,
  and reviewable.
- **Members:** [Confirm final roster and roles; working attribution: Varun
  (WP1), Dhrishit (WP2), Harshit (WP3), Aayush (WP4)]

**Talk track:** ModelProof is our response to the challenge of reviewing
legacy models with incomplete evidence while keeping consequential decisions
with people.

## Slide 2 — The problem and three work tracks

**On slide**

- A Tier 1 UK-bank estate of [X: metrics.json inventory (model count)] models
  across legacy SAS, R, and Python.
- Each validation takes [X: metrics.json validation_weeks_min] to
  [X: metrics.json validation_weeks_max] weeks;
  documentation can be outdated or incomplete.
- Governance context: PRA SS1/23.
- **Hackathon tracks:** GenAI and Agents; Predictive Analytics; Responsible AI.

**Talk track:** The challenge spans documentation, redevelopment, and
validation; ModelProof connects the work while supporting the hackathon tracks.

## Slide 3 — USP: evidence, checks, oversight

**On slide**

- **01 — Different:** start from legacy SAS and R code; make every output
  traceable to evidence or deterministic checks.
- **02 — How it helps:** assemble an evidence pack quickly so validators can
  focus on judgment instead of manual document chasing.
- **03 — USP:** “LLMs propose, deterministic code disposes.”

**Talk track:** The system proposes and organizes evidence; deterministic
engines check it, and people retain accountable review decisions.

## Slide 4 — Four features, one gated flow

**On slide**

- **Inventory:** browse models and risk/security findings.
- **Deterministic tiering:** assign risk tiers from the fixed policy matrix.
- **Evidence documentation:** inspect claims, source excerpts, and code drift.
- **Parity-certified rebuild:** review attempts, localiser feedback, and parity.
- **One-click validation and monitoring:** inspect RAG checks, fairness, and
  drift signals.

**Five-stage flow:** Discover → Document → Redevelop → Validate → Monitor

**Human gates:** a reviewer gate separates every stage; monitoring can route a
trigger back to Validate. Automation does not approve a model for production.

**Talk track:** The features map to the five workflow stages, with human review
where decisions require accountability.

## Slide 5 — Architecture and technology

**On slide**

- **UI:** Streamlit pages for inventory, model detail, review, audit, and the
  business case.
- **Artifact path:** app data adapter reads generated JSON artifacts and
  presents evidence, checks, and metrics.
- **Workflow and validation stack:** Python; LangGraph/checkpointing per the
  project contract; pandas/NumPy; scikit-learn/Fairlearn; Pydantic.
- **Runtime LLM:** provider/model [confirm with Varun]; credentials stay in
  environment configuration.
- **Estimated runtime LLM cost per model:** [X: metrics.json
  llm_usage.total.cost_usd / count(metrics.json inventory)] — calculated from
  measured aggregate runtime cost and model inventory; not validator labour
  cost.

**Talk track:** The visible workbench reads generated artifacts and separates
them from deterministic checks and human decisions. Confirm the deployment
architecture and cost basis before describing either as final.

## Slide 6 — Inventory, injection finding, and drift

**On slide**

- [Screenshot placeholder: Inventory model list and selected model record]
- [Screenshot placeholder: seeded injection/security finding]
- [Screenshot placeholder: Documentation tab with source evidence and
  documentation-to-code drift]
- The injection/security finding is seeded demonstration content, not a
  production incident.

**Talk track:** Show where a reviewer finds a model, inspects a seeded
security-related finding, and traces a documentation/code discrepancy. Do not
present seeded content as a live incident.

## Slide 7 — Redevelopment: self-healing attempt and parity

**On slide**

- [Screenshot placeholder: redevelopment attempt results and localiser
  feedback illustrating the self-healing loop]
- [Screenshot placeholder: five-level parity certificate]
- Describe recovery or parity outcomes only if the real generated artifacts
  shown on screen substantiate them.

**Talk track:** The attempt view records feedback and outcomes; the certificate
organizes parity evidence across its levels. A screenshot or LLM claim alone
does not establish a successful rebuild.

## Slide 8 — Validation, fairness, and PSI trigger

**On slide**

- [Screenshot placeholder: Validation tab with RAG results and fairness
  findings]
- [Screenshot placeholder: Monitoring tab with PSI series and trigger]
- The demo's drift trigger is simulated; do not describe it as production
  monitoring evidence.

**Talk track:** Review the RAG checks and fairness findings together, then show
how the simulated PSI signal leads to a revalidation handoff. Interpret
subgroup findings as prompts for investigation, not conclusions.

## Slide 9 — Three headline metrics and responsible AI

**Headline metrics — populate from a verified real run only**

- **Accuracy vs seeded ground truth:** [X: metrics.json
  inventory_accuracy.deterministic.accuracy]
  Definition: deterministic inventory-field accuracy against the seeded gold
  labels; show the measured numerator and denominator from that artifact.
- **Time per model:** [X: metrics.json runtime.live.total_s / count(metrics.json inventory)]
  Definition: live-run elapsed seconds divided by the number of models in the
  inventory; confirm the run and scope shown in the artifact.
- **Models per hour:** [X: metrics.json count(inventory) / runtime.live.total_s converted to hours]
  Definition: number of inventoried models divided by live-run elapsed hours.

**Responsible AI**

- Benchmark and seeded synthetic inputs are not bank customer records.
- Keep protected attributes out of model inputs; review fairness signals with
  context.
- LLM output is fallible; use evidence, deterministic checks, and human
  approval. Demo injection findings and drift are seeded or simulated.

**Talk track:** These are the only headline metrics. The real metrics file is
not available here, so all values, keys, units, and evaluation scope must be
confirmed before presentation.

## Slide 10 — Business case, roadmap, and links

**On slide**

- **Calculator assumptions:** models in estate; validations per model per year;
  weeks per validation; validator effort automated; cost per validator week.
  Outputs are scenario estimates, not measured savings.
- **Estimated validator cost per model:** [X: business-case calculator output;
  enter assumptions in the app].
- **Roadmap:** confirm data provenance/licences and runtime configuration; run
  the workflow with real artifacts; validate metric definitions; refine gated
  review and monitoring from reviewer feedback.
- **GitHub:** [Repository URL to confirm]
- **Live demo:** [Deployment URL to confirm]
- **Video:** [Recording URL to confirm]

**Talk track:** The calculator makes its assumptions visible, and the roadmap
starts with evidence and configuration that still need confirmation. Replace
the links with approved destinations before sharing the deck.
