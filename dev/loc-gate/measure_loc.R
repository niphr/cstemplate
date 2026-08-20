.libPaths(c("/tmp/loclib", .libPaths()))
EXTS <- c("R", "r", "S", "s", "q")
PATT <- paste0("\\.(", paste(EXTS, collapse = "|"), ")$")

old_select <- function(d) sort(Sys.glob(file.path(d, "R", "*.R")))
new_select <- function(d) {
  f <- list.files(file.path(d, "R"), all.files = FALSE)
  sort(file.path(d, "R", grep(PATT, f, value = TRUE)))
}

pkgs <- c(file.path("/home/raw996/niphr", c("cs9","cs9example","csalert","csdata","csdb",
                                            "csmaps","csstyle","cstidy","cstime","csutil")),
          file.path("/home/raw996/wb", c("cohort","org","plnr")))

cat(sprintf("%-12s %5s %5s %6s %8s %8s %s\n",
            "package", "n_old", "n_new", "delta", "max_old", "max_new", "newly covered (loc)"))
tot <- 0
for (d in pkgs) {
  o <- old_select(d); n <- new_select(d)
  add <- setdiff(n, o)
  co <- if (length(o)) org::loc_per_file(o) else integer(0)
  cn <- if (length(n)) org::loc_per_file(n) else integer(0)
  ca <- if (length(add)) org::loc_per_file(add) else integer(0)
  tot <- tot + length(add)
  cat(sprintf("%-12s %5d %5d %6d %8d %8d %s\n",
              basename(d), length(o), length(n), length(add),
              if (length(co)) max(co) else 0L, if (length(cn)) max(cn) else 0L,
              if (length(add)) paste(sprintf("%s(%d)", basename(add), ca), collapse = " ") else ""))
}
cat("\nnewly covered files, total:", tot, "\n")
cat("any package max over 1000:",
    any(sapply(pkgs, function(d) { n <- new_select(d); if (!length(n)) return(FALSE)
      max(org::loc_per_file(n)) > 1000 })), "\n")
cat("\n--- also: does old != new selection differ ONLY by added files (never removed)?\n")
for (d in pkgs) {
  o <- old_select(d); n <- new_select(d)
  rem <- setdiff(o, n)
  if (length(rem)) cat("REMOVED from", basename(d), ":", paste(rem, collapse = " "), "\n")
}
cat("(no REMOVED line means the new selection is a strict superset everywhere)\n")
