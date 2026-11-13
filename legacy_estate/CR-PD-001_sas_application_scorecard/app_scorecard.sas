/* app_scorecard.sas - application scorecard, unsecured retail, v1.2        */
/* RT 2019-06. WoE values pasted from the 2019 dev run, do not retrain      */
libname raw    "/data/raw/credit";
libname scored "/data/scored/cr001";

/* cutoff 520 per Credit Committee Mar-2018 */
%LET CUTOFF = 540;
%LET PDO = 20;
%LET BASE_SCORE = 600;
%LET BASE_ODDS = 30;

DATA work.german;
  SET raw.german_credit;
  IF ranuni(12345) < 0.7 THEN sample = 'DEV'; ELSE sample = 'VAL';

  /* WoE recodes */
  IF checking_status = '<0' THEN w_chk = -0.8181;
  ELSE IF checking_status = '0<=X<200' THEN w_chk = -0.4014;
  ELSE IF checking_status = '>=200' THEN w_chk = 0.4055;
  ELSE w_chk = 1.1763;

  IF duration <= 12 THEN w_dur = 0.4674;
  ELSE IF duration <= 24 THEN w_dur = 0.0151;
  ELSE w_dur = -0.6202;

  IF credit_history IN ('all paid', 'no credits/all paid') THEN w_hist = -1.2400;
  ELSE IF credit_history IN ('existing paid', 'delayed previously') THEN w_hist = -0.0880;
  ELSE w_hist = 0.7337;

  IF savings_status = '<100' THEN w_sav = -0.2714;
  ELSE IF savings_status = '100<=X<500' THEN w_sav = -0.1396;
  ELSE IF savings_status IN ('500<=X<1000', '>=1000') THEN w_sav = 0.9000;
  ELSE w_sav = 0.7042;

  IF personal_status = 'female div/dep/mar' THEN w_pstat = -0.2353;
  ELSE IF personal_status = 'male div/sep' THEN w_pstat = -0.4418;
  ELSE IF personal_status = 'male mar/wid' THEN w_pstat = 0.1385;
  ELSE w_pstat = 0.1655;

  IF age <= 25 THEN w_age = -0.5288;
  ELSE IF age <= 35 THEN w_age = 0.0168;
  ELSE w_age = 0.2643;

  debt_ratio = installment_commitment * credit_amount / 100;
RUN;

DATA work.dev; SET work.german; WHERE sample = 'DEV'; RUN;

PROC LOGISTIC DATA=work.dev DESCENDING OUTMODEL=work.lgmodel;
  MODEL bad = w_chk w_dur w_hist w_sav w_pstat w_age / SELECTION=NONE;
RUN;

PROC LOGISTIC INMODEL=work.lgmodel;
  SCORE DATA=work.german OUT=work.pred;
RUN;

DATA scored.app_grades;
  SET work.pred;
  factor = &PDO / LOG(2);
  offset = &BASE_SCORE - factor * LOG(&BASE_ODDS);
  score = ROUND(offset + factor * LOG((1 - p_1) / p_1));
  IF score >= 590 THEN grade = 'A';
  ELSE IF score >= 565 THEN grade = 'B';
  ELSE IF score >= 540 THEN grade = 'C';
  ELSE IF score >= 515 THEN grade = 'D';
  ELSE grade = 'E';
  decision = (score >= &CUTOFF);
  KEEP ID grade score p_1 decision bad sample;
RUN;
