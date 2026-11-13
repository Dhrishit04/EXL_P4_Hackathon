# legacy_parity (WP2)

Simulated legacy model estate, data, ground truth and the R goldens.

| Path | What |
| --- | --- |
| `legacy_estate/` | four simulated legacy models (SAS, R, Python) with seeded issues |
| `data/` | processed CSVs (committed), `DATA_CARD.md`; `raw/` is gitignored |
| `eval/gold/` | ground truth for evaluation, never read by `src/` or `prompts/` |
| `scripts/fetch_data.py` | rebuilds `data/` (`uv run python legacy_parity/scripts/fetch_data.py`) |
| `WP2_PROMPT.md` | the WP2 task brief |

Python modules stay in the shared package because `modelproof.*` imports are the contract:
`src/modelproof/{data,security,sandbox,parity}.py`, `extract/`, `agents/redevelop.py`, `prompts/redevelop.md`,
`tests/test_{data,gold,extract,sandbox,parity,redevelop}.py`.
