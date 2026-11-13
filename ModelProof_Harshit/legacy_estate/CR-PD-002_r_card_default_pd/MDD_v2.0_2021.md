# Model Development Document: Behavioural PD Scorecard, Card Book (CR-PD-002)

Version 2.0, March 2021. Owner: Card Credit Risk.

## 1. Purpose
Estimates the 12 month probability of default (PD) of existing credit card customers for limit management and collections strategy.

## 2. Data
30,000 card accounts. Payment histories cover January to June 2004; the default outcome is observed in July 2004.
The target is `DEFAULT`, defined as 90 or more days past due within the following 12 months.
70% of accounts form the development sample and 30% the holdout, stratified on the target.

## 3. Methodology
Characteristics are grouped into bins and replaced by weight of evidence (WoE), with 0.5 added to the counts of any bin that has no goods or no bads.
A logistic regression (binomial GLM) is fitted on the WoE values.
The model characteristics are: the payment ratio, number of delinquent months, worst payment status, age band, credit limit band and customer education.
Missing payment ratios (no positive bill) are given their own MISSING bin.
SEX and MARRIAGE are not used.

## 4. Scoring
Scores are scaled so that 600 points correspond to odds of 50:1 and 25 points double the odds (PDO 25).
Scores are truncated to whole points.

## 5. Decision
Customers scoring 580 or more are approved. Grades A to G are assigned by score band.

## 6. Limitations
The model is calibrated to a 2004 Taiwan card population and should be monitored for drift every quarter.
