# Model Development Document: Application Scorecard (CR-PD-001)

Version 1.2, June 2019. Owner: Retail Credit Risk.

## 1. Purpose
Rank-orders applicants for unsecured personal loans by probability of default (PD) and supports the approve / decline decision.

## 2. Data
German Credit extract, 1,000 applications, target `bad` (1 = defaulted).
The development sample is an 80% random split with a 20% validation sample.

## 3. Methodology
Weight of evidence (WoE) recodes of the predictors feed a logistic regression (PROC LOGISTIC, DESCENDING).
The predictors are: checking status, loan duration, credit history, savings status, property magnitude and age.
No demographic or protected characteristics are used in the model.

## 4. Scoring
Scorecard scaling uses 40 points to double the odds (PDO 40), anchored at 600 points for odds of 30:1.
Scores are rounded to the nearest integer, ties to even (banker's rounding).

## 5. Decision
Applicants scoring 520 or more are approved. Grades A to E are assigned by score band.

## 6. Limitations
The model was developed on a small sample and has not been recalibrated since 2019.
