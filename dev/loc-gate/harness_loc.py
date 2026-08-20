#!/usr/bin/env python3
"""Run the LOC gate step against fixture packages.

The step body is read from the YAML via yaml.safe_load, so the text under test
is the text that ships. Every fixture runs against BOTH bodies:

  OLD  the committed step at cstemplate HEAD, which globs "R/*.R"
  NEW  the working-tree step

The step declares `shell: Rscript {0}`, so the runner writes the block to a file
and runs `Rscript <file>`. The harness does the same.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

NEW_TEMPLATE = "/home/raw996/niphr/cstemplate/.github/workflows/r-package.yml"
OLD_TEMPLATE = "/tmp/phase6b/loc-old-r-package.yml"
ORG_LIB = "/tmp/loclib"
ROOT = "/tmp/phase6b/locfx"


def extract_step(path):
    doc = yaml.safe_load(open(path))
    steps = doc["jobs"]["loc-limit"]["steps"]
    hits = [s for s in steps
            if s.get("name", "").startswith("Check the code lines")]
    assert len(hits) == 1, (path, len(hits))
    assert hits[0]["shell"] == "Rscript {0}", hits[0]["shell"]
    return hits[0]["run"]


def lines(n):
    """n code lines, plus a comment and a blank that must not be counted."""
    return "# a comment\n\n" + "".join("x%d <- %d\n" % (i, i) for i in range(n))


def build(name, files, extra_dirs=()):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if files is not None:
        os.makedirs(os.path.join(d, "R"))
        for rel, content in files.items():
            full = os.path.join(d, "R", rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as fh:
                fh.write(content)
    for sub in extra_dirs:
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def run(body, d, max_loc="1000", allowlist=""):
    script = os.path.join(d, "step.R")
    with open(script, "w") as fh:
        fh.write(body)
    env = dict(os.environ)
    env.update({"ORG_LIB": ORG_LIB, "MAX_LOC": max_loc, "LOC_ALLOWLIST": allowlist})
    return subprocess.run(["Rscript", "step.R"], cwd=d, env=env,
                          capture_output=True, text=True)


CHECKED = re.compile(r"Checked (\d+) files against a limit of (\S+)\. "
                     r"The maximum is (\d+)\.")


def parse(p):
    m = CHECKED.search(p.stdout or "")
    return (int(m.group(1)), int(m.group(3))) if m else (None, None)


# ---- fixtures --------------------------------------------------------------
# Each: (name, files, max_loc, allowlist, want_new, note)
# want_new is (exit, n_files, max_loc_found) or (exit, stderr_substring)

BIG = lines(10)
SMALL = lines(3)

FIXTURES = [
    ("L1-baseline-dot-R", {"a.R": SMALL}, "1000", "", (0, 1, 3)),
    ("L2-lowercase-dot-r", {"a.R": SMALL, "b.r": lines(7)}, "1000", "", (0, 2, 7)),
    ("L3-uppercase-dot-S", {"a.R": SMALL, "b.S": lines(8)}, "1000", "", (0, 2, 8)),
    ("L4-lowercase-dot-s", {"a.R": SMALL, "b.s": lines(9)}, "1000", "", (0, 2, 9)),
    ("L5-lowercase-dot-q", {"a.R": SMALL, "b.q": lines(6)}, "1000", "", (0, 2, 6)),
    ("L6-all-five-at-once",
     {"a.R": SMALL, "b.r": SMALL, "c.S": SMALL, "d.s": SMALL, "e.q": lines(4)},
     "1000", "", (0, 5, 4)),
    # The regression test for this block.
    ("L7-dot-r-OVER-the-limit", {"a.R": SMALL, "big.r": BIG}, "5", "",
     (1, "R/big.r")),
    ("L8-dot-R-over-the-limit-still-fails", {"big.R": BIG}, "5", "",
     (1, "R/big.R")),
    ("L9-dot-q-over-the-limit", {"a.R": SMALL, "big.q": BIG}, "5", "",
     (1, "R/big.q")),
    ("L10-non-code-extensions-ignored",
     {"a.R": SMALL, "vig.Rmd": BIG, "doc.Rd": BIG, "notes.txt": BIG,
      "readme.md": BIG, "data.RData": BIG, "x.Rprofile": BIG},
     "5", "", (0, 1, 3)),
    ("L11-empty-R-directory", {}, "1000", "", (1, "so the limit checked nothing")),
    ("L12-no-R-directory", None, "1000", "", (1, "so the limit checked nothing")),
    ("L13-dotfiles-ignored",
     {"a.R": SMALL, ".DS_Store": BIG, ".hidden.R": BIG}, "5", "", (0, 1, 3)),
    # Allowlist, both directions, on the newly covered extension.
    ("L14-allowlist-exempts-a-dot-r-file",
     {"a.R": SMALL, "big.r": BIG}, "5", "R/big.r", (0, 2, 10)),
    ("L15-allowlist-stale-entry-fails",
     {"a.R": SMALL, "big.r": BIG}, "5", "R/gone.r",
     (1, "These loc-allowlist entries name no file in R/")),
    ("L16-allowlist-live-entry-not-called-stale",
     {"a.R": SMALL, "big.r": BIG, "big2.R": BIG}, "5", "R/big.r\nR/big2.R",
     (0, 3, 10)),
    ("L17-allowlist-entry-for-dot-S",
     {"a.R": SMALL, "big.S": BIG}, "5", "R/big.S", (0, 2, 10)),
    # R collates lowercase .q only. An uppercase .Q MUST NOT be counted.
    ("L18-uppercase-dot-Q-not-collated",
     {"a.R": SMALL, "big.Q": BIG}, "5", "", (0, 1, 3)),
    # Pinned difference from R: R also drops a basename that does not start
    # with an alphanumeric. This gate keeps it, which is the stricter side.
    ("L19-underscore-prefix-counted-here",
     {"a.R": SMALL, "_helper.R": lines(4)}, "1000", "", (0, 2, 4)),
]


def check(want, p):
    if len(want) == 3:
        e, n, mx = want
        gn, gmx = parse(p)
        return (p.returncode == e and gn == n and gmx == mx,
                "exit=%s n=%s max=%s" % (p.returncode, gn, gmx))
    e, sub = want
    got = (p.stderr or "") + (p.stdout or "")
    return (p.returncode == e and sub in got,
            "exit=%s substr=%s" % (p.returncode, sub in got))


def main():
    new = extract_step(NEW_TEMPLATE)
    old = extract_step(OLD_TEMPLATE)
    assert new != old, "old and new step bodies are identical"
    print("OLD step body from %s" % OLD_TEMPLATE)
    print("NEW step body from %s" % NEW_TEMPLATE)
    print("=" * 78)
    print("%-38s %-28s %s" % ("fixture", "NEW (expected)", "OLD (same input)"))
    print("=" * 78)
    bad = 0
    for name, files, max_loc, allow, want in FIXTURES:
        d = build(name, files)
        pn = run(new, d, max_loc, allow)
        ok, desc = check(want, pn)
        d2 = build(name + "-old", files)
        po = run(old, d2, max_loc, allow)
        on, omx = parse(po)
        odesc = "exit=%s n=%s max=%s" % (po.returncode, on, omx)
        bad += 0 if ok else 1
        print("%-38s %-28s %s%s"
              % (name, desc + ("  PASS" if ok else "  FAIL"), odesc,
                 "   <-- DIFFERS" if (po.returncode, on, omx) !=
                 (pn.returncode, *parse(pn)) else ""))
        if not ok:
            print("    STDERR: %s" % (pn.stderr or "").strip()[:400])
    print("=" * 78)
    print("LOC FIXTURE FAILURES: %d of %d" % (bad, len(FIXTURES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
