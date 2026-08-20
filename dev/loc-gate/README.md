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
| `harness_loc.py` | 19 fixtures for the code-line gate |
| `mutations_loc.py` | 8 mutations of the gate |
| `casefold.R` | proves the file selection does not depend on filesystem case-folding |
| `sortcheck.R` | proves `list.files()` already returns collation order |
| `measure_loc.R` | counts what the gate sees, per package |
| `p4check_repinned2.py` | asserts all 13 callers are wired and pinned |
| `probepkg/` | a minimal package with sentinel tokens, the input to fixture F8 |

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

Then:

```bash
python3 dev/loc-gate/harness2.py
python3 dev/loc-gate/mutations2.py
python3 dev/loc-gate/harness_loc.py
python3 dev/loc-gate/mutations_loc.py
```

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

## Known gaps

**The gate does not look in `R/unix/` or `R/windows/`.** R collates those subdirectories. No
package in the fleet has one, so the invariant holds today. A package that adds one reopens the
hole, and closing it needs its own fixtures.

**The gate counts `R/_helper.R`, which R does not collate**, because `list_files_with_type()`
drops any basename not starting with an alphanumeric. Stricter than R, so it cannot let an
over-limit file through. Fixture `L19` pins it.

**`mutations_loc.py` reports `N8` as unproven.** It removes a `sort()` that cannot be made to
matter. Recorded as unpinned rather than given a decorative assertion.
