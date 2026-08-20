#!/usr/bin/env python3
"""Mutation proofs for the LOC gate. Break one thing, name the fixtures that go red."""
import contextlib
import importlib.util
import io
import os
import sys

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "harness_loc.py")
spec = importlib.util.spec_from_file_location("hl", HARNESS)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

BODY = h.extract_step(h.NEW_TEMPLATE)

CANARY = '''if (exists(".make_file_exts", envir = asNamespace("tools"), inherits = FALSE)) {
  r_exts <- tools:::.make_file_exts("code")
  if (!setequal(r_exts, code_exts)) {
    stop(
      "R collates these code extensions: ", paste(r_exts, collapse = " "),
      "\\nThis gate checks: ", paste(code_exts, collapse = " "),
      "\\nUpdate code_exts in the workflow.",
      call. = FALSE
    )
  }
}
'''
EXTS_LINE = 'code_exts <- c("R", "r", "S", "s", "q")\n'
SELECT = '''files <- character()
for (d in c("R", "R/unix", "R/windows")) {
  found <- list.files(d, all.files = FALSE)
  files <- c(files, file.path(d, grep(pattern, found, value = TRUE)))
}
files <- sort(files)
'''
DIRS_LINE = 'for (d in c("R", "R/unix", "R/windows")) {\n'
GATHER = 'files <- c(files, file.path(d, grep(pattern, found, value = TRUE)))\n'

# The selection as it stood before it covered the OS subdirectories. N9 puts
# it back, which is the revert this block exists to keep red.
TOPLEVEL_ONLY = '''files <- list.files("R", all.files = FALSE)
files <- sort(file.path("R", grep(pattern, files, value = TRUE)))
'''

for nm, frag in [("CANARY", CANARY), ("EXTS_LINE", EXTS_LINE),
                 ("SELECT", SELECT), ("DIRS_LINE", DIRS_LINE),
                 ("GATHER", GATHER)]:
    assert frag in BODY, "%s not found in the step body" % nm

MUTATIONS = [
    ("N1 revert the selection to sort(Sys.glob(\"R/*.R\"))",
     BODY.replace(SELECT, 'files <- sort(Sys.glob("R/*.R"))\n')),
    ("N2 drop \"q\" from code_exts, canary in place",
     BODY.replace(EXTS_LINE, 'code_exts <- c("R", "r", "S", "s")\n')),
    ("N3 drop \"q\" AND remove the canary",
     BODY.replace(EXTS_LINE, 'code_exts <- c("R", "r", "S", "s")\n').replace(CANARY, "")),
    ("N4 drop \"r\" AND remove the canary",
     BODY.replace(EXTS_LINE, 'code_exts <- c("R", "S", "s", "q")\n').replace(CANARY, "")),
    ("N5 match the extension case-insensitively",
     BODY.replace('grep(pattern, found, value = TRUE)',
                  'grep(pattern, found, value = TRUE, ignore.case = TRUE)')),
    ("N6 list.files(all.files = TRUE), so dotfiles enter",
     BODY.replace('list.files(d, all.files = FALSE)',
                  'list.files(d, all.files = TRUE)')),
    ("N7 return bare basenames instead of the path",
     BODY.replace(GATHER,
                  'files <- c(files, grep(pattern, found, value = TRUE))\n')),
    ("N8 remove the sort()",
     BODY.replace('files <- sort(files)\n', '')),
    # ---- the OS subdirectory coverage ---------------------------------------
    ("N9 revert to R/ only, the selection before this coverage",
     BODY.replace(SELECT, TOPLEVEL_ONLY)),
    ("N10 check the runner's OS subdirectory only",
     BODY.replace(DIRS_LINE,
                  'for (d in c("R", file.path("R", tools:::.OStype()))) {\n')),
    # N10 resolves to "unix" on this runner, so it cannot show that R/unix/ is
    # covered. N11 drops the other side, and the two red sets are disjoint.
    ("N11 drop R/unix/, keeping R/windows/",
     BODY.replace(DIRS_LINE, 'for (d in c("R", "R/windows")) {\n')),
    ("N12 check every subdirectory of R/, not the two R collates",
     BODY.replace(DIRS_LINE, 'for (d in list.dirs("R", recursive = TRUE)) {\n')),
    ("N13 recurse below the OS subdirectory",
     BODY.replace('list.files(d, all.files = FALSE)',
                  'list.files(d, all.files = FALSE, recursive = TRUE)')),
]


def verdicts(body):
    out = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for name, files, max_loc, allow, want, extra in map(h.unpack,
                                                            h.FIXTURES):
            d = h.build(os.path.join("mut", name), files, extra)
            p = h.run(body, d, max_loc, allow)
            out[name] = h.check(want, p)[0]
    return out


base = verdicts(BODY)
print("### BASELINE, shipped step body")
for k, ok in base.items():
    print("  %-42s %s" % (k, "PASS" if ok else "FAIL"))
assert all(base.values()), "baseline is not green, so no mutation proof is valid"
print()

unproven = []
for label, body in MUTATIONS:
    assert body != BODY, "%s changed nothing" % label
    v = verdicts(body)
    red = sorted(k for k in v if not v[k])
    print("### %s" % label)
    if not red:
        print("  UNPROVEN: no fixture changed verdict")
        unproven.append(label)
    else:
        print("  RED-FIXTURES (%d): %s" % (len(red), ", ".join(red)))
    print()

print("MUTATIONS WITH NO RED FIXTURE: %d of %d" % (len(unproven), len(MUTATIONS)))
for u in unproven:
    print("  UNPROVEN: %s" % u)
sys.exit(0)
