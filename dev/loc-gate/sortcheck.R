# What does sort() do in the shipped selection, and does anything depend on it?
#
# Before the step read the OS subdirectories, sort() sorted one already
# collated listing and was a no-op. It now joins three listings that arrive
# concatenated, so it reorders. That makes the question live: does the order
# reach any decision, or only the text of an error message?
#
# This script reads the order out of the shipped step rather than a copy of
# it. With max-loc set to 0 every file is over the limit, so the step's own
# error enumerates the whole selection in its final order.
#
# Needs org at /tmp/loclib. See README.md.

TEMPLATE <- "/home/raw996/niphr/cstemplate/.github/workflows/r-package.yml"
ORG_LIB <- "/tmp/loclib"

extract_step <- function(path) {
  d <- yaml::yaml.load_file(path)
  st <- d$jobs[["loc-limit"]]$steps
  nms <- vapply(
    st,
    function(s) if (is.null(s$name)) "" else s$name,
    character(1)
  )
  h <- st[startsWith(nms, "Check the code lines")]
  stopifnot(length(h) == 1, h[[1]]$shell == "Rscript {0}")
  h[[1]]$run
}

# Names chosen so the concatenated order and the sorted order differ. zeta.R
# sits last in R/ and last overall, but every subdirectory path sorts before
# it, so a missing sort() is visible.
FILES <- c("zeta.R", "alpha.R", "unix/mid.r", "windows/beta.S")

d <- file.path(tempdir(), "sortcheck")
unlink(d, recursive = TRUE)
for (sub_dir in c("R", "R/unix", "R/windows")) {
  dir.create(file.path(d, sub_dir), recursive = TRUE)
}
for (f in FILES) {
  writeLines("x <- 1", file.path(d, "R", f))
}
old <- setwd(d)
on.exit(setwd(old))

# Sys.setenv, never system2(env=). An allowlist holds one path per LINE, and
# system2() builds a shell prefix, so a newline inside a value breaks the
# command it constructs.
run_step <- function(body, max_loc, allowlist) {
  cat(body, file = "step.R")
  Sys.setenv(ORG_LIB = ORG_LIB, MAX_LOC = max_loc, LOC_ALLOWLIST = allowlist)
  on.exit(Sys.unsetenv(c("ORG_LIB", "MAX_LOC", "LOC_ALLOWLIST")))
  suppressWarnings(system2("Rscript", "step.R", stdout = TRUE, stderr = TRUE))
}

# max_loc = 0 puts every file over the limit, so the step lists all of them.
selection_order <- function(body, allowlist = "") {
  out <- run_step(body, "0", allowlist)
  hits <- grep("^\\s+R/\\S+ \\([0-9]+\\)$", out, value = TRUE)
  trimws(sub(" \\([0-9]+\\)$", "", hits))
}

stale_report <- function(body, allowlist) {
  out <- run_step(body, "1000", allowlist)
  trimws(grep("^\\s+R/\\S+$", out, value = TRUE))
}

body <- extract_step(TEMPLATE)

cat("LC_COLLATE:", Sys.getlocale("LC_COLLATE"), "\n")
cat("files on disk:", length(FILES), "\n\n")

# Measure the shipped body FIRST, never behind a shape check. A step that lost
# its sort() is what this script exists to catch, so the reading below must
# happen before anything can stop.
shipped <- selection_order(body)
cat(
  "shipped order, read from the step's own error:\n  ",
  paste(shipped, collapse = " "),
  "\n"
)

# The same body with sort() removed. This is mutation N8 in mutations_loc.py,
# which no fixture there can make red.
SORT_LINE <- "files <- sort(files)\n"
has_sort <- grepl(SORT_LINE, body, fixed = TRUE)
if (!has_sort) {
  cat("NOTE: the step no longer holds `files <- sort(files)`.\n")
  cat(
    "      The unsorted contrast is skipped. Read the shipped order above.\n\n"
  )
  nosort <- shipped
} else {
  UNSORTED <- sub(SORT_LINE, "", body, fixed = TRUE)
  nosort <- selection_order(UNSORTED)
  cat("order with sort() removed:\n  ", paste(nosort, collapse = " "), "\n\n")
  cat("sort() reorders the selection:", !identical(shipped, nosort), "\n")
  cat("same SET either way          :", setequal(shipped, nosort), "\n\n")
}

# The order question that matters: does either ordering change a decision?
# Direction 1 is setdiff(allowlist, files), which names stale entries.
# Direction 2 is names(counts) %in% allowlist, which exempts a file.
ALLOW <- "R/windows/beta.S\nR/unix/gone.r"
OTHER <- if (has_sort) UNSORTED else body
cat("allowlist: R/windows/beta.S (live), R/unix/gone.r (stale)\n")
s1 <- stale_report(body, ALLOW)
s2 <- stale_report(OTHER, ALLOW)
cat("  stale, sorted  :", paste(s1, collapse = " "), "\n")
cat("  stale, unsorted:", paste(s2, collapse = " "), "\n")

e1 <- setdiff(shipped, selection_order(body, "R/windows/beta.S"))
e2 <- setdiff(nosort, selection_order(OTHER, "R/windows/beta.S"))
cat("  exempted, sorted  :", paste(e1, collapse = " "), "\n")
cat("  exempted, unsorted:", paste(e2, collapse = " "), "\n\n")

ok <- c(
  "shipped order is the sorted order" = identical(shipped, sort(shipped)),
  "stale set does not depend on order" = identical(s1, s2),
  "exempt set does not depend on order" = setequal(e1, e2)
)
if (has_sort) {
  ok <- c(
    ok,
    "sort() does real work now" = !identical(shipped, nosort),
    "same selection either way" = setequal(shipped, nosort)
  )
}
for (k in names(ok)) {
  cat(sprintf("%-38s %s\n", k, ok[[k]]))
}
cat("\nSORTCHECK FAILURES:", sum(!ok), "of", length(ok), "\n")
if (any(!ok)) {
  quit(status = 1)
}
