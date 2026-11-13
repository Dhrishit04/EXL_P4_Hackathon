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
