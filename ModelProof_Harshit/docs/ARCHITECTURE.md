# Architecture

The legacy estate and processed data are the inputs to the ModelProof workflow.
Discover extracts deterministic facts and proposes an inventory record.
Document creates evidence-linked documentation, then a human gate reviews it.
Redevelop translates the rebuild target in a sandbox and checks parity.
Validation runs policy-driven performance, stability, and fairness checks.
Monitoring tracks simulated drift and can return a model to validation.
A human approval gate separates each workflow stage.
The LLM proposes content using source code and aggregate information only.
It never receives row-level data or determines numeric results or risk tiers.
Deterministic engines include extractors, injection scanning, tiering, claim
verification, sandboxing, parity, metrics, fairness, and policy evaluation.
Artifacts and a hash-chained audit log provide traceability for the workbench.
Validation metrics can also be recorded in MLflow.
The Streamlit workbench presents evidence, outcomes, and pending approvals.

The corresponding flow is in [architecture.mmd](./architecture.mmd).
