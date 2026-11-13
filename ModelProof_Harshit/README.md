# ModelProof validation and reporting

Harshit's project files for model validation, fairness assessment, risk tiering, simulated monitoring and printable reports.

- `src/modelproof/` contains the implementation.
- `tests/` contains offline tests and synthetic fixtures.
- `config/policy.yaml` contains the fixed thresholds.
- `CONTRACT.md` defines integration interfaces.
- `artifacts/` holds generated results.

Run commands from this directory.

```powershell
uv sync --all-extras
uv run pytest -q
```

For integration into the shared project, use the contents of this directory as the project root. Runtime paths resolve relative to this directory.

## Integration status

The offline tests use synthetic data and a test-only data-module stand-in. Running the complete validation workflow requires the team data loaders, processed development/holdout data, rebuilt scorer and parity certificate. The command-line module on this branch currently provides `verify-audit`; the integrated workflow commands arrive with the shared application.

Set `LLM_MODEL` to a valid model id for the selected provider before running the integrated agents.
