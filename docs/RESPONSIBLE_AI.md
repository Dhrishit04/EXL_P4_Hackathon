# Responsible AI

## Data sources, licences, and privacy

The demonstration uses public benchmark datasets and seeded synthetic card
transactions; it is not connected to bank customer data. The repository does
not contain `data/DATA_CARD.md` or the source data files, so the exact versions,
provenance, and licence applicability cannot be verified here. Confirm each
entry below against the data card before external distribution.

- **Taiwan credit-card default:** Yeh, I. (2009). *Default of Credit Card
  Clients* [Dataset]. UCI Machine Learning Repository, dataset 350.
  [DOI: 10.24432/C55S3H](https://doi.org/10.24432/C55S3H). The related paper
  is Yeh, I. C., & Lien, C. H. (2009), “The comparisons of data mining
  techniques for the predictive accuracy of probability of default of credit
  card clients,” *Expert Systems with Applications*, 36(2), 2473–2480,
  [DOI: 10.1016/j.eswa.2007.12.020](https://doi.org/10.1016/j.eswa.2007.12.020).
  [Dataset record](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients).
  **Licence:** CC BY 4.0 as listed by UCI — TODO: confirm against
  `data/DATA_CARD.md` (Dhrishit).
- **German credit:** Hofmann, H. (1994). *Statlog (German Credit Data)*
  [Dataset]. UCI Machine Learning Repository, dataset 144.
  [DOI: 10.24432/C5NC77](https://doi.org/10.24432/C5NC77).
  [UCI dataset record](https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data);
  also available as [OpenML `credit-g` (dataset 31)](https://www.openml.org/d/31).
  The OpenML record identifies the German credit benchmark corresponding to
  the Statlog source.   **UCI licence:** CC BY 4.0 — TODO: confirm against
  `data/DATA_CARD.md` (Dhrishit).
  **OpenML licence:** the dataset record lists “Public” — TODO: confirm
  against `data/DATA_CARD.md` (Dhrishit).
- **Card transactions:** project-generated synthetic transactions, seeded for
  repeatable demonstration use; no third-party transaction dataset is intended.
  **Licence:** project terms and any source material are unverified — TODO:
  confirm against `data/DATA_CARD.md` (Dhrishit).

No row-level records are sent to the runtime language model. Provider
credentials belong in environment variables and must not be committed.

## Security and integrity

Generated code is intended to be checked by the AST-based sandbox and run
without network access. The injection scanner flags suspicious source text.
These controls reduce risk but do not prove generated code is safe. Prompt and
document content are untrusted inputs. Evidence, deterministic checks, and
human review remain necessary.

## Fairness and limitations

The validation design includes fairness tests by sex, age band, marital status,
and education. Protected attributes must not be used as model inputs. The
seeded `personal_status` proxy is an example finding requiring investigation,
not a conclusion about a production model. Age-band analysis can obscure
within-band effects and must be interpreted with care. Taiwan default data from
2005 may not represent current populations or the bank's customers.

The LLM can be wrong; generated claims are subject to evidence verification,
and numeric results and risk tiers are produced by deterministic code. SAS is
not executed without an appropriate licence. Monitoring drift in the demo is
simulated, and planted documentation errors are seeded test cases.

## Human oversight and transparency

Human approval gates govern workflow stages. `--auto-approve` is a demo option
whose use must be recorded in the audit log; it does not approve any model for
production. The hash-chained audit log supports tamper detection. Cached prompts
and responses support review, subject to secret and data-handling controls.

The workbench is an illustrative decision-support tool, not a substitute for
independent validation, governance approval, or regulatory assessment.
