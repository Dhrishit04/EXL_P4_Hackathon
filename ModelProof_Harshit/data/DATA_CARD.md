# Data card

Regenerate with `python scripts/fetch_data.py` (seed 42). Raw downloads go to `data/raw/` (gitignored); processed files are committed.
`cr_pd_002_edge.csv` is written by `legacy_estate/CR-PD-002_r_card_default_pd/make_edge.R` and hashed in the parity certificate.

## Sources
| Dataset | Source | Licence / citation |
| --- | --- | --- |
| Taiwan Default of Credit Card Clients (CR-PD-002) | UCI ML Repository id 350 (`ucimlrepo`; fallback OpenML 42477 via `fairlearn`) | CC BY 4.0. Yeh, I.C. and Lien, C.H. (2009), *The comparisons of data mining techniques for the predictive accuracy of probability of default of credit card clients*, Expert Systems with Applications 36(2). |
| German Credit (CR-PD-001, PR-RB-004) | OpenML `credit-g` v1 (Statlog German Credit, Hofmann) | UCI / OpenML public data. `bad` = 1 if class is `bad` (30% of rows). |
| Synthetic card fraud (FR-TX-003) | `scripts/fetch_data.py::fraud` | Generated, no real customers. Process is written in the script docstring. |

## Files
| File | Rows | Columns | SHA-256 |
| --- | --- | --- | --- |
| `cr_pd_002_dev.csv` | 21,000 | 25 | `86e0648681501f6398d8329a273fbb2477e3905d76dc54be3759e4246af9ff02` |
| `cr_pd_002_holdout.csv` | 9,000 | 25 | `4d4176ae6c0040770e397b6b38f08cdbbae1528304b12ca8d13967d8bef41b47` |
| `german_credit.csv` | 1,000 | 22 | `8307e3620f25e35f98cb75aff1f3ceb4b53896dff2215028f803d058e7641fdd` |
| `fraud_transactions.csv` | 50,000 | 9 | `754ff4ea81cac8759fa96b347a04598b98d7a565242aada60f156497725de15a` |

Taiwan: 30,000 rows, default rate 0.2212, stratified 70/30 split (21,000 dev / 9,000 holdout), `ID` is source row order 1..30000.
Columns follow the UCI X1..X23 order renamed to `LIMIT_BAL, SEX, EDUCATION, MARRIAGE, AGE, PAY_0, PAY_2..PAY_6, BILL_AMT1..6, PAY_AMT1..6` plus `DEFAULT`; the mapping is checked by assertions in `fetch_data.py`.
Fraud: 50,000 rows, 457 fraud (0.914%) with seed 42.

## Limitations
* Taiwan data is a 2005 credit card population, not UK retail. It stands in for a behavioural PD book.
* German Credit is 1,000 rows from the 1990s; it is only used to give the SAS models something to run on.
* Fraud data is fully synthetic, with a hand-written risk formula, so model accuracy says nothing about real fraud.
* Nothing here is production data; all statistics are for demonstrating the process.
