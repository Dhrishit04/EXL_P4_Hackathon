# pd_model.R -- behavioural PD scorecard, card book (CR-PD-002) v2.3
# base R only. dev sample -> WoE bins -> glm -> score. last touched 2021-03 JK
# NB: do not change cut points without Credit Policy sign off

CUT_UTIL  <- c(0, 0.25, 0.5, 0.75, 1)       # cut(), right closed
CUT_PAYR  <- c(0.02, 0.1, 0.5, 1)           # findInterval(), left closed
CUT_AGE   <- c(25, 30, 40, 50)              # findInterval(), left closed
CUT_LIMIT <- c(50000, 100000, 200000)       # ifelse chain, left closed
PAY_COLS  <- c("PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6")

PDO <- 20            # PDO 25 per policy memo CP-14
BASE_SCORE <- 600
BASE_ODDS <- 25      # good:bad at BASE_SCORE
CUTOFF <- 560        # approve if score >= CUTOFF
GRADE_CUTS <- c(500, 520, 540, 560, 565, 570)   # -> G F E D C B A

fmt <- function(x) vapply(x, format, "", scientific = FALSE, trim = TRUE)

# bin spec: label / lower / upper / closed, one row per bin
spec <- function(feature, cuts, closed) {
  lo <- c(-Inf, cuts); hi <- c(cuts, Inf)
  lab <- if (closed == "right") sprintf("(%s,%s]", fmt(lo), fmt(hi)) else sprintf("[%s,%s)", fmt(lo), fmt(hi))
  data.frame(feature = feature, bin_label = lab, lower = lo, upper = hi, closed = closed, stringsAsFactors = FALSE)
}

mk_specs <- function() {
  rbind(
    spec("util", CUT_UTIL, "right"),
    spec("pay_ratio", CUT_PAYR, "left"),
    data.frame(feature = "pay_ratio", bin_label = "MISSING", lower = NA_real_, upper = NA_real_, closed = "none", stringsAsFactors = FALSE),
    data.frame(feature = "n_delinq", bin_label = c("0", "1", "2-3", "4+"), lower = c(0, 1, 2, 4), upper = c(0, 1, 3, Inf),
               closed = c("both", "both", "both", "left"), stringsAsFactors = FALSE),
    data.frame(feature = "worst_status", bin_label = c("<=0", "1", "2", "3+"), lower = c(-Inf, 1, 2, 3), upper = c(0, 1, 2, Inf),
               closed = c("right", "both", "both", "left"), stringsAsFactors = FALSE),
    spec("age_band", CUT_AGE, "left"),
    spec("limit_band", CUT_LIMIT, "left")
  )
}

derive <- function(d) {
  pay <- d[, PAY_COLS]
  o <- data.frame(ID = d$ID)
  o$util <- d$BILL_AMT1 / d$LIMIT_BAL
  o$pay_ratio <- ifelse(d$BILL_AMT1 <= 0, NA, d$PAY_AMT1 / d$BILL_AMT1)
  o$n_delinq <- rowSums(pay > 0)
  o$worst_status <- do.call(pmax, unname(as.list(pay)))
  o$AGE <- d$AGE
  o$LIMIT_BAL <- d$LIMIT_BAL
  o$avg_bill <- rowMeans(d[, paste0("BILL_AMT", 1:6)])   # for the 2020 monitoring pack
  o
}

bin_all <- function(f) {
  sp <- mk_specs()
  L <- function(feat) sp$bin_label[sp$feature == feat]
  b <- data.frame(ID = f$ID)
  b$util <- as.character(cut(f$util, c(-Inf, CUT_UTIL, Inf), labels = L("util"), right = TRUE))
  b$pay_ratio <- ifelse(is.na(f$pay_ratio), "MISSING", L("pay_ratio")[findInterval(f$pay_ratio, CUT_PAYR) + 1])
  b$n_delinq <- ifelse(f$n_delinq == 0, "0", ifelse(f$n_delinq == 1, "1", ifelse(f$n_delinq <= 3, "2-3", "4+")))
  b$worst_status <- ifelse(f$worst_status <= 0, "<=0", ifelse(f$worst_status == 1, "1", ifelse(f$worst_status == 2, "2", "3+")))
  b$age_band <- L("age_band")[findInterval(f$AGE, CUT_AGE) + 1]
  lb <- L("limit_band")
  b$limit_band <- ifelse(f$LIMIT_BAL < CUT_LIMIT[1], lb[1], ifelse(f$LIMIT_BAL < CUT_LIMIT[2], lb[2],
                  ifelse(f$LIMIT_BAL < CUT_LIMIT[3], lb[3], lb[4])))
  b
}

# WoE = ln(%good / %bad); 0.5 added to both counts when a bin has no goods or no bads
woe_tables <- function(bins, y) {
  sp <- mk_specs()
  do.call(rbind, lapply(unique(sp$feature), function(ft) {
    s <- sp[sp$feature == ft, ]
    lab <- factor(bins[[ft]], levels = s$bin_label)
    s$n <- as.numeric(table(lab))
    s$n_bad <- as.numeric(tapply(y, lab, sum)); s$n_bad[is.na(s$n_bad)] <- 0
    ng <- s$n - s$n_bad
    z <- s$n_bad == 0 | ng == 0
    s$woe <- log(((ng + 0.5 * z) / sum(ng)) / ((s$n_bad + 0.5 * z) / sum(s$n_bad)))
    s
  }))
}

WOE_VARS <- c(util = "woe_util", pay_ratio = "woe_pay_ratio", n_delinq = "woe_n_delinq",
              worst_status = "woe_worst_status", age_band = "woe_age", limit_band = "woe_limit")

apply_woe <- function(bins, wt) {
  o <- data.frame(ID = bins$ID)
  for (ft in names(WOE_VARS)) {
    s <- wt[wt$feature == ft, ]
    o[[WOE_VARS[[ft]]]] <- s$woe[match(bins[[ft]], s$bin_label)]
  }
  o
}

fit_model <- function(woe, y) {
  d <- cbind(woe, DEFAULT = y)
  glm(DEFAULT ~ woe_util + woe_pay_ratio + woe_n_delinq + woe_worst_status + woe_age + woe_limit,
      family = binomial, data = d)
}

score_model <- function(woe, coefs) {
  eta <- coefs[["(Intercept)"]]
  for (v in WOE_VARS) eta <- eta + coefs[[v]] * woe[[v]]
  pd <- plogis(eta)
  factor <- PDO / log(2)
  offset <- BASE_SCORE - factor * log(BASE_ODDS)
  score <- round(offset + factor * log((1 - pd) / pd))      # R rounds half to even
  grade <- c("G", "F", "E", "D", "C", "B", "A")[findInterval(score, GRADE_CUTS) + 1]
  data.frame(ID = woe$ID, pd = pd, score = score, grade = grade,
             decision = ifelse(score >= CUTOFF, "approve", "decline"), stringsAsFactors = FALSE)
}
