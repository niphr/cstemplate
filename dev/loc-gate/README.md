# Tests for the reusable workflow

`../../.github/workflows/r-package.yml` is called by 16 packages. It has two steps that are easy
to break silently, and this directory is the evidence they work.

Every harness extracts the step body from the workflow YAML with `yaml.safe_load`, so it tests the
shipped text rather than a copy that can drift.

## What is here

| File | Covers |
|---|---|
| `harness2.py` | 15 fixtures for the step that keeps agent instructions off the site |
| `mutations2.py` | 10 mutations of that step, each red in at least one fixture |
| `harness_loc.py` | 36 fixtures for the code-line gate |
| `mutations_loc.py` | 13 mutations of the gate |
| `casefold.R` | 4 checks that the selection does not depend on filesystem case folding |
| `sortcheck.R` | 5 checks on what `sort()` does, and on whether any decision reads the order |
| `measure_loc.R` | runs the gate against every package it guards, and reports the verdict |
| `p4check_repinned2.py` | asserts all 13 callers are wired and pinned |
| `probepkg/` | a minimal package with sentinel tokens, the input to fixture F8 |

**Every one of these extracts the step from the YAML and runs it.** None holds a copy of the
selection. `casefold.R`, `sortcheck.R` and `measure_loc.R` reimplemented it until 2026-08-20,
which let them drift from the shipped step in a way the two Python harnesses never could.

Three rules the R scripts follow, and each was a bug first:

- **Read the block scalar with `cat()`, never `writeLines()`.** The YAML already ends the block
  in a newline, so `writeLines()` adds a second one and the extracted text stops matching what
  Python extracts.
- **Pass the allowlist with `Sys.setenv()`, never `system2(env=)`.** An allowlist holds one path
  per line, `system2()` builds a shell prefix, and a newline inside a value breaks the command.
- **Measure the shipped body before any shape check.** A step that no longer holds the block a
  script wants to swap is the case that script exists to catch. Stopping above the measurement
  turns the finding into a crash that names the wrong thing.

## Run them

The harnesses need a rendered site for F8, which is not committed because it is build output.
Regenerate it first:

```bash
R CMD INSTALL -l /tmp/probelib dev/loc-gate/probepkg
cd dev/loc-gate/probepkg
RSTUDIO_PANDOC=/opt/quarto/bin/tools Rscript -e '
  .libPaths(c("/tmp/probelib", .libPaths()))
  pkgdown::build_site_github_pages(".", new_process = FALSE, install = FALSE)'
```

**pandoc 3 or newer is required.** pandoc 2.9.2.1 fails `build_llm_docs()` with
`pandoc document conversion failed with error 23` and stops before writing any `.md` sibling. It
reads as a pkgdown bug rather than a missing dependency, and it costs an hour to work out. The
pandoc bundled with quarto is new enough.

The code-line harnesses call `org::loc_per_file()`, so they need `org` at `/tmp/loclib`, built
from the SHA the workflow pins. Never install it into your own library:

```bash
mkdir -p /tmp/loclib /tmp/orgsrc
git -C ~/wb/org archive 33f76369f6eceb9fcb1eb7734500e52450e27384 | tar -x -C /tmp/orgsrc
R CMD INSTALL -l /tmp/loclib /tmp/orgsrc
```

Then:

```bash
python3 dev/loc-gate/harness2.py
python3 dev/loc-gate/mutations2.py
python3 dev/loc-gate/harness_loc.py
python3 dev/loc-gate/mutations_loc.py
python3 dev/loc-gate/p4check_repinned2.py
Rscript  dev/loc-gate/casefold.R
Rscript  dev/loc-gate/sortcheck.R
Rscript  dev/loc-gate/measure_loc.R
```

`casefold.R` and `sortcheck.R` exit non-zero on a failed check, so they run in a script.
`measure_loc.R` reports and always exits zero: two rows read `FAIL`, because `cstemplate` and
`rwtemplate` carry no `R/` directory. Neither calls the workflow.

**`p4check_repinned2.py` holds the two pinned SHAs.** Update both constants whenever the
callers are re-pinned, or the check passes against the version it was written for.

## Why each step is shaped the way it is

**Five files carry the agent instructions, not one.** `CLAUDE.html`, `PROJECT.html`, `CLAUDE.md`,
`PROJECT.md` and `search.json`. Established by rendering `probepkg` with sentinel tokens and
grepping the whole site. `docs/CLAUDE.md` is not a copy of the root file: `build_llm_docs()` globs
`*.html` recursively and converts each to a `.md` sibling with pandoc.

**`search.json` is filtered on the `path` field, never on the text.** A surviving page may
legitimately mention `CLAUDE.md`, and `cs9`'s changelog does, three times. A text filter deletes
published changelog entries from the search index.

**Under `set -e`, a pipeline beginning with `!` never aborts the script.** So `! grep -q ...` is
inert unless it is the step's literal last command. Every assertion uses
`if ...; then exit 1; fi`, which is live wherever it sits. Mutation `M4` pins this.

**The gate selects files the way R does.** `tools:::.make_file_exts("code")` returns
`R r S s q`, and R uses `list.files()` plus a case-sensitive `grep()`, not a glob. A union of
globs returns nine paths for five files on a case-folding filesystem, so it double-counts on
macOS. `casefold.R` measures that.

A canary compares the step's extension list against R's on every run, so a sixth extension in a
future R fails the job loudly rather than narrowing the gate in silence.

**The gate reads `R/`, `R/unix/` and `R/windows/`, and no other directory.** R collates an OS
subdirectory of `R/` as package code, so a glob of `R/` alone cannot see a file there.

The choice to read both, rather than the runner's own OS, comes from R's behaviour rather than
from the manual. Three measurements settled it:

1. `R CMD INSTALL` on Linux collates `R/unix/u.R` and not `R/windows/w.R`. Verified by installing
   a probe package: `unix_fn` exists in the namespace, `windows_fn` does not.
2. `R CMD check` on the same machine reads `R/windows/w.R`. A syntax error there fails
   `checking R files for syntax errors`. `tools:::.check_package_code_syntax()` passes
   `OS_subdirs = c("unix", "windows")`, where `.install_package_code_files()` takes the
   `.OStype()` default.
3. `R/helpers/h.R` is collated by neither. Verified the same way: `helper_fn` is absent.

So R's own precedent for a check is both directories, and this gate is a check. Every job in the
workflow runs on `ubuntu-latest`, so a runner-OS gate never looks in `R/windows/` on any run. It
also calls a `loc-allowlist` entry for a file there stale, which leaves that file no way to be
exempted. Fixture `L26` pins that second surface, and mutation `N10` keeps it red.

## Known gaps

**The gate counts `R/_helper.R`, which R does not collate**, because `list_files_with_type()`
drops any basename not starting with an alphanumeric. Stricter than R, so it cannot let an
over-limit file through. Fixture `L19` pins it.

**`mutations_loc.py` reports `N8` as unproven.** It removes the `sort()`. That call now does real
work, because it interleaves three directory listings that arrive concatenated. Nothing
downstream reads the order: `setdiff(allowlist, files)` and `names(counts) %in% allowlist` both
answer the same under either ordering, measured. Only the order of names inside an error message
changes, so no fixture verdict can move.

`sortcheck.R` does catch the removal, from a different angle. It reads the order out of the
step's own error message, with `max-loc` set to `0` so every file is listed. It then checks that
the order is the sorted order. Remove `files <- sort(files)` from the workflow and that check
reports `FALSE` and exits 1. So the gap is in `mutations_loc.py` alone, not in the suite.

**The step has no canary on the OS subdirectory names**, unlike the one on the extension list.
`.OStype()` reports the runner's own OS only, so on `ubuntu-latest` such a canary can report
`unix` and nothing else. It cannot fire for the case it exists for: a future R that collates a
third subdirectory name. A check that cannot go red was left out.

**The step has no `dir.exists()` guard on the OS subdirectories.** `list.files()` returns
`character(0)` for a path that is absent, and for a path that is a plain file, with no warning in
either case. A guard there changed no fixture verdict, so it was removed rather than kept as a
line the suite cannot defend.
