#!/usr/bin/env python3
"""Mutation proofs for the LOC gate. Break one thing, name the fixtures that go red."""
import contextlib
import importlib.util
import io
import os
import sys

spec = importlib.util.spec_from_file_location("hl", "/tmp/phase6b/harness_loc.py")
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
SELECT = '''pattern <- paste0("\\\\.(", paste(code_exts, collapse = "|"), ")$")
files <- list.files("R", all.files = FALSE)
files <- sort(file.path("R", grep(pattern, files, value = TRUE)))
'''

for nm, frag in [("CANARY", CANARY), ("EXTS_LINE", EXTS_LINE), ("SELECT", SELECT)]:
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
     BODY.replace('grep(pattern, files, value = TRUE)',
                  'grep(pattern, files, value = TRUE, ignore.case = TRUE)')),
    ("N6 list.files(all.files = TRUE), so dotfiles enter",
     BODY.replace('list.files("R", all.files = FALSE)', 'list.files("R", all.files = TRUE)')),
    ("N7 return bare basenames instead of R/<name>",
     BODY.replace('files <- sort(file.path("R", grep(pattern, files, value = TRUE)))',
                  'files <- sort(grep(pattern, files, value = TRUE))')),
    ("N8 remove the sort()",
     BODY.replace('files <- sort(file.path("R", grep(pattern, files, value = TRUE)))',
                  'files <- file.path("R", grep(pattern, files, value = TRUE))')),
]


def verdicts(body):
    out = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for name, files, max_loc, allow, want in h.FIXTURES:
            d = h.build(os.path.join("mut", name), files)
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
