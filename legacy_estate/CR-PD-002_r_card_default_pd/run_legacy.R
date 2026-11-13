# run_legacy.R -- fit on dev, score dev / holdout / edge, write golden/ (17 significant digits)
args <- commandArgs(FALSE)
here <- dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)])))
root <- normalizePath(file.path(here, "..", ".."))
source(file.path(here, "pd_model.R"))
source(file.path(here, "make_edge.R"))
gold <- file.path(here, "golden"); dir.create(gold, showWarnings = FALSE)
rd <- function(s) read.csv(file.path(root, "data", "processed", paste0("cr_pd_002_", s, ".csv")))
dev <- rd("dev")
f17 <- function(x) sprintf("%.17g", x)

fd <- derive(dev); bd <- bin_all(fd)
wt <- woe_tables(bd, dev$DEFAULT)
fit <- fit_model(apply_woe(bd, wt), dev$DEFAULT)
coefs <- as.list(coef(fit))

co <- data.frame(term = names(coefs), estimate = f17(unlist(coefs)))
write.csv(co, file.path(gold, "coefficients.csv"), row.names = FALSE, quote = FALSE)
w <- wt; w$lower <- f17(w$lower); w$upper <- f17(w$upper); w$woe <- f17(w$woe)
w$lower[w$closed == "none"] <- ""; w$upper[w$closed == "none"] <- ""
write.csv(w[, c("feature", "bin_label", "lower", "upper", "closed", "n", "n_bad", "woe")],
          file.path(gold, "woe_tables.csv"), row.names = FALSE, quote = TRUE)

for (s in c("dev", "holdout", "edge")) {
  d <- rd(s); b <- bin_all(derive(d))
  sc <- score_model(apply_woe(b, wt), coefs)
  sc$pd <- f17(sc$pd); sc$score <- f17(sc$score)
  write.csv(sc, file.path(gold, paste0("scored_", s, ".csv")), row.names = FALSE, quote = FALSE)
}
sink(file.path(gold, "r_session.txt")); print(sessionInfo()); print(summary(fit)); sink()
