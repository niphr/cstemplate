# Does the shipped selection survive a case-insensitive filesystem?
# Sys.glob() hands the match to the OS. On macOS "R/*.R" matches foo.r.
# This script simulates that by folding case in a stub, then runs both
# candidate implementations against the same directory.
EXTS <- c("R", "r", "S", "s", "q")
PATT <- paste0("\\.(", paste(EXTS, collapse = "|"), ")$")

d <- tempfile(); dir.create(file.path(d, "R"), recursive = TRUE)
for (f in c("a.R", "b.r", "c.S", "d.s", "e.q")) writeLines("x <- 1", file.path(d, "R", f))
owd <- setwd(d); on.exit(setwd(owd))

glob_sensitive <- function(pattern) {
  ext <- sub("^R/\\*\\.", "", pattern)
  f <- list.files("R")
  file.path("R", f[grepl(paste0("\\.", ext, "$"), f)])          # case-SENSITIVE
}
glob_folding <- function(pattern) {
  ext <- sub("^R/\\*\\.", "", pattern)
  f <- list.files("R")
  file.path("R", f[grepl(paste0("\\.", ext, "$"), f, ignore.case = TRUE)])
}

naive <- function(glob) sort(unlist(lapply(EXTS, function(e) glob(paste0("R/*.", e)))))
shipped <- function(glob) {
  f <- list.files("R", all.files = FALSE)
  sort(file.path("R", grep(PATT, f, value = TRUE)))             # never calls glob
}

cat("files on disk: 5 (a.R b.r c.S d.s e.q)\n\n")
for (nm in c("naive union of five globs", "shipped list.files + grep")) {
  fn <- if (grepl("naive", nm)) naive else shipped
  a <- fn(glob_sensitive); b <- fn(glob_folding)
  cat(sprintf("%-28s case-sensitive FS: n=%d unique=%d | case-folding FS: n=%d unique=%d\n",
              nm, length(a), length(unique(a)), length(b), length(unique(b))))
}
cat("\nnaive selection under a case-folding filesystem:\n")
print(naive(glob_folding))
cat("\nshipped selection under a case-folding filesystem:\n")
print(shipped(glob_folding))
cat("\nduplicates in naive under case-folding:",
    sum(duplicated(naive(glob_folding))), "\n")
cat("duplicates in shipped under case-folding:",
    sum(duplicated(shipped(glob_folding))), "\n")
