d <- file.path(tempdir(), "sortcheck")
unlink(d, recursive = TRUE)
dir.create(file.path(d, "R"), recursive = TRUE)
for (f in c("zeta.R", "Alpha.r", "mid.S", "beta.q", "Gamma.s")) {
  writeLines("x <- 1", file.path(d, "R", f))
}
setwd(d)
PATT <- "\\.(R|r|S|s|q)$"
raw <- list.files("R", all.files = FALSE)
cat("raw list.files():", paste(raw, collapse = " "), "\n")
a <- file.path("R", grep(PATT, raw, value = TRUE))
b <- sort(a)
cat("LC_COLLATE:", Sys.getlocale("LC_COLLATE"), "\n")
cat("without sort():", paste(a, collapse = " "), "\n")
cat("with    sort():", paste(b, collapse = " "), "\n")
cat("identical:", identical(a, b), "\n")
cat("same SET either way:", setequal(a, b), "\n")
