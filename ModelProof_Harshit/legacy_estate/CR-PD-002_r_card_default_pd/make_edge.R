# make_edge.R -- raw rows that land exactly on every cut point and one unit either side.
# LIMIT_BAL = 100000 for the ratio rows so util and pay_ratio are exact in floating point.
# (sourced by run_legacy.R: expects `here` and `root`)
source(file.path(here, "pd_model.R"))
base <- list(LIMIT_BAL = 100000, SEX = 1, EDUCATION = 2, MARRIAGE = 1, AGE = 35,
             PAY_0 = 0, PAY_2 = 0, PAY_3 = 0, PAY_4 = 0, PAY_5 = 0, PAY_6 = 0,
             BILL_AMT1 = 40000, BILL_AMT2 = 40000, BILL_AMT3 = 40000, BILL_AMT4 = 40000, BILL_AMT5 = 40000, BILL_AMT6 = 40000,
             PAY_AMT1 = 2000, PAY_AMT2 = 2000, PAY_AMT3 = 2000, PAY_AMT4 = 2000, PAY_AMT5 = 2000, PAY_AMT6 = 2000)
rows <- list()
add <- function(...) { r <- base; v <- list(...); r[names(v)] <- v; rows[[length(rows) + 1]] <<- as.data.frame(r) }
for (c in CUT_UTIL) for (d in -1:1) add(BILL_AMT1 = round(c * 100000) + d)
for (c in CUT_PAYR) for (d in -1:1) add(PAY_AMT1 = round(c * 40000) + d)
for (c in CUT_AGE) for (d in -1:1) add(AGE = c + d)
add(AGE = 21); add(AGE = 79)
for (c in CUT_LIMIT) for (d in -1:1) add(LIMIT_BAL = c + d, BILL_AMT1 = 10000)
add(LIMIT_BAL = 10000); add(LIMIT_BAL = 1000000)
for (k in 0:6) { p <- setNames(as.list(c(rep(1, k), rep(0, 6 - k))), PAY_COLS); do.call(add, p) }
for (v in -2:8) add(PAY_0 = v)
for (v in c(-2, -1, 1, 2, 3, 8)) do.call(add, setNames(as.list(rep(v, 6)), PAY_COLS))
for (b in c(0, -1, -1000, -165580)) for (p in c(0, 2000)) add(BILL_AMT1 = b, PAY_AMT1 = p)
add(BILL_AMT1 = 964511, PAY_AMT1 = 873552)
edge <- do.call(rbind, rows)
edge <- cbind(ID = 900000 + seq_len(nrow(edge)), edge, DEFAULT = 0)
write.csv(edge, file.path(root, "data", "processed", "cr_pd_002_edge.csv"), row.names = FALSE)
