# What does the gate see in each package it guards?
#
# This runs the shipped step body, extracted from the YAML, once per package,
# with the workflow's own default limit. It is the CI gate, on this machine,
# against the real trees. It reports what each package would get.
#
# The script writes its step file to tempdir() and only changes directory into
# each package, so it leaves no file behind in any repo.
#
# Needs org at /tmp/loclib. See README.md.

TEMPLATE <- "/home/raw996/niphr/cstemplate/.github/workflows/r-package.yml"
ORG_LIB <- "/tmp/loclib"

`%||%` <- function(a, b) if (is.null(a)) b else a

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

# The workflow's own default for max-loc, read from the YAML rather than
# copied, so this cannot drift from the number the callers get.
#
# The key is d[[TRUE]], not d$on. YAML 1.1 reads a bare `on` as the boolean
# true, so the trigger block arrives under a logical name.
default_max_loc <- function(path) {
  d <- yaml::yaml.load_file(path)
  trig <- d[[TRUE]] %||% d$on
  as.character(trig$workflow_call$inputs[["max-loc"]]$default)
}

STEP <- file.path(tempdir(), "measure_step.R")
cat(extract_step(TEMPLATE), file = STEP)
MAX <- default_max_loc(TEMPLATE)

pkgs <- Sys.glob(c("/home/raw996/niphr/*", "/home/raw996/wb/*"))
pkgs <- pkgs[file.exists(file.path(pkgs, "DESCRIPTION"))]

run_in <- function(d) {
  old <- setwd(d)
  on.exit(setwd(old))
  Sys.setenv(ORG_LIB = ORG_LIB, MAX_LOC = MAX, LOC_ALLOWLIST = "")
  on.exit(Sys.unsetenv(c("ORG_LIB", "MAX_LOC", "LOC_ALLOWLIST")), add = TRUE)
  out <- suppressWarnings(system2(
    "Rscript",
    STEP,
    stdout = TRUE,
    stderr = TRUE
  ))
  list(out = out, status = attr(out, "status") %||% 0L)
}

cat("shipped step from:", TEMPLATE, "\n")
cat("max-loc default  :", MAX, "\n\n")
cat(sprintf(
  "%-14s %6s %6s %8s  %s\n",
  "package",
  "gate",
  "files",
  "max_loc",
  "OS subdirs"
))

fails <- character()
for (d in pkgs) {
  r <- run_in(d)
  hit <- grep("Checked ", r$out, value = TRUE)
  n <- if (length(hit)) {
    as.integer(sub(".*Checked ([0-9]+) files.*", "\\1", hit[1]))
  } else {
    NA_integer_
  }
  mx <- if (length(hit)) {
    as.integer(sub(".*maximum is ([0-9]+).*", "\\1", hit[1]))
  } else {
    NA_integer_
  }
  subs <- c("R/unix", "R/windows")[dir.exists(file.path(
    d,
    c("R/unix", "R/windows")
  ))]
  verdict <- if (r$status == 0L) "PASS" else "FAIL"
  if (r$status != 0L) {
    fails <- c(fails, basename(d))
  }
  cat(sprintf(
    "%-14s %6s %6s %8s  %s\n",
    basename(d),
    verdict,
    if (is.na(n)) "-" else n,
    if (is.na(mx)) "-" else mx,
    if (length(subs)) paste(subs, collapse = " ") else "none"
  ))
}

cat("\npackages the gate fails:", length(fails), "of", length(pkgs), "\n")
for (f in fails) {
  cat("  ", f, "\n")
}
cat(
  "\nA package with no R/ directory fails by design: the limit checked nothing.\n"
)
