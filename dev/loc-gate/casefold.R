# Does the shipped selection survive a case-insensitive filesystem?
#
# Sys.glob() hands the match to the OS. On macOS "R/*.R" matches foo.r, so a
# union of five globs returns nine paths for five files. The shipped step is
# immune because it never calls Sys.glob() at all.
#
# This script proves that by execution, not by reading. It extracts the step
# body from the YAML, defines a case-folding Sys.glob() above it, and runs the
# two together. R resolves an unqualified Sys.glob() to the global definition
# first, so the stub fires if the body ever reaches for it. A body that never
# calls it leaves the counter at zero and counts each file once.
#
# Needs org at /tmp/loclib. See README.md.

TEMPLATE <- "/home/raw996/niphr/cstemplate/.github/workflows/r-package.yml"
ORG_LIB <- "/tmp/loclib"

# The exact selection block. Kept as a literal so the naive contrast below is
# a fixed-string swap, and so this script fails loudly if the step is reshaped.
SELECT <- 'files <- character()
for (d in c("R", "R/unix", "R/windows")) {
  found <- list.files(d, all.files = FALSE)
  files <- c(files, file.path(d, grep(pattern, found, value = TRUE)))
}
files <- sort(files)'

NAIVE <- 'files <- sort(unlist(lapply(code_exts, function(e) Sys.glob(paste0("R/*.", e)))))'

# cat(), never writeLines(). The YAML block scalar already ends in a newline,
# and writeLines() adds a second one.
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

STUB <- 'GLOB_CALLS <- 0L
Sys.glob <- function(paths, dirmark = FALSE) {
  GLOB_CALLS <<- GLOB_CALLS + 1L
  # A case-folding filesystem matches foo.r against "R/*.R".
  out <- character()
  for (p in paths) {
    dd <- dirname(p)
    ext <- sub("^.*\\\\*\\\\.", "", p)
    f <- list.files(dd, all.files = FALSE)
    out <- c(out, file.path(dd, f[grepl(paste0("\\\\.", ext, "$"), f, ignore.case = TRUE)]))
  }
  out
}'

TAIL <- 'cat("SYS.GLOB CALLS:", GLOB_CALLS, "\\n")'

# Five extensions across the three directories the gate reads. Each name is one
# file on disk.
#
# The subdirectory count is deliberate. Five files in R/ make a folding glob
# union return 9 paths, so a fixture with 9 files total lets a reverted
# selection report the right number by coincidence. Ten breaks the tie.
FILES <- c(
  "a.R",
  "b.r",
  "c.S",
  "d.s",
  "e.q",
  "unix/f.R",
  "unix/g.r",
  "windows/h.S",
  "windows/i.q",
  "windows/j.r"
)

d <- file.path(tempdir(), "casefold")
unlink(d, recursive = TRUE)
for (sub_dir in c("R", "R/unix", "R/windows")) {
  dir.create(file.path(d, sub_dir), recursive = TRUE)
}
for (f in FILES) {
  writeLines("x <- 1", file.path(d, "R", f))
}
old <- setwd(d)
on.exit(setwd(old))

run <- function(body) {
  cat(STUB, body, TAIL, sep = "\n", file = "step.R")
  suppressWarnings(system2(
    "Rscript",
    "step.R",
    env = c(paste0("ORG_LIB=", ORG_LIB), "MAX_LOC=1000", "LOC_ALLOWLIST="),
    stdout = TRUE,
    stderr = TRUE
  ))
}

grab <- function(out, patt) {
  hit <- grep(patt, out, value = TRUE)
  if (!length(hit)) {
    return(NA_integer_)
  }
  as.integer(sub(patt, "\\1", hit[1]))
}

body <- extract_step(TEMPLATE)

cat(
  "files on disk:",
  length(FILES),
  "\n  ",
  paste(FILES, collapse = " "),
  "\n\n"
)

# Measure the shipped body FIRST, and never behind a shape check. A step that
# no longer holds SELECT is exactly the case this script exists to catch, so
# it must reach the Sys.glob counter rather than stop above it.
cat("--- shipped body, under a case-folding Sys.glob() stub ---\n")
out <- run(body)
cat(paste(out, collapse = "\n"), "\n\n")

# The contrast needs the selection block to swap out. Losing it is reportable,
# not fatal.
has_select <- grepl(SELECT, body, fixed = TRUE)
if (!has_select) {
  cat("NOTE: the step no longer holds the expected selection block.\n")
  cat(
    "      The naive contrast is skipped. Read the shipped numbers above.\n\n"
  )
  out2 <- character()
} else {
  naive <- sub(SELECT, NAIVE, body, fixed = TRUE)
  stopifnot(naive != body)
  cat("--- a union of five globs, same stub, same directory ---\n")
  out2 <- run(naive)
  cat(paste(out2, collapse = "\n"), "\n\n")
}

CHECKED <- ".*Checked ([0-9]+) files.*"
CALLS <- ".*SYS.GLOB CALLS: ([0-9]+).*"
n <- grab(out, CHECKED)
n2 <- grab(out2, CHECKED)
calls <- grab(out, CALLS)
calls2 <- grab(out2, CALLS)

# Each count needs its own base. The shipped selection reads three
# directories, the naive one globs R/ alone, and the two bases differ. Both
# happen to report 9 here, which is why neither number means anything on its
# own.
n_all <- length(FILES)
n_top <- sum(!grepl("/", FILES))

cat("files on disk in R/, R/unix/ and R/windows/:", n_all, "\n")
cat("files on disk in R/ alone                  :", n_top, "\n\n")
cat(
  "shipped: Sys.glob calls =",
  calls,
  " counted",
  n,
  "against a base of",
  n_all,
  "\n"
)
cat(
  "naive  : Sys.glob calls =",
  calls2,
  " counted",
  n2,
  "against a base of",
  n_top,
  "\n\n"
)

ok <- c(
  "shipped never calls Sys.glob" = identical(calls, 0L),
  "shipped counts each file once" = identical(n, n_all)
)
if (has_select) {
  ok <- c(
    ok,
    "naive calls Sys.glob once per ext" = identical(calls2, 5L),
    "naive double counts under folding" = isTRUE(n2 > n_top)
  )
}
for (k in names(ok)) {
  cat(sprintf("%-36s %s\n", k, ok[[k]]))
}
cat("\nCASEFOLD FAILURES:", sum(!ok), "of", length(ok), "\n")
if (any(!ok)) {
  quit(status = 1)
}
