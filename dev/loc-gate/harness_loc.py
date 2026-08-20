#!/usr/bin/env python3
"""Run the LOC gate step against fixture packages.

The step body is read from the YAML via yaml.safe_load, so the text under test
is the text that ships. Every fixture runs against BOTH bodies:

  OLD  the committed step at cstemplate HEAD, which globs "R/*.R"
  NEW  the working-tree step

The step declares `shell: Rscript {0}`, so the runner writes the block to a file
and runs `Rscript <file>`. The harness does the same.
"""
import os
import re
import shutil
import subprocess
import sys

import yaml

REPO = "/home/raw996/niphr/cstemplate"
NEW_TEMPLATE = os.path.join(REPO, ".github/workflows/r-package.yml")
# The step as it stood before it selected files the way R does. Read from git,
# so the comparison column cannot rot when a /tmp copy is cleared.
OLD_REF = "5c082c5:.github/workflows/r-package.yml"
OLD_TEMPLATE = "/tmp/loc-gate/loc-old-r-package.yml"
ORG_LIB = "/tmp/loclib"
ROOT = "/tmp/loc-gate/locfx"


def materialise_old():
    os.makedirs(os.path.dirname(OLD_TEMPLATE), exist_ok=True)
    text = subprocess.run(["git", "-C", REPO, "show", OLD_REF],
                          capture_output=True, text=True, check=True).stdout
    with open(OLD_TEMPLATE, "w") as fh:
        fh.write(text)


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
# Each: (name, files, max_loc, allowlist, want_new[, extra_dirs])
# want_new is (exit, n_files, max_loc_found) or (exit, stderr_substring)
# extra_dirs holds package-relative directories to create empty, and defaults
# to none.

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
    # ---- the OS subdirectories R collates -----------------------------------
    # R/unix/ is what R CMD INSTALL collates on this runner.
    ("L20-unix-subdir-under-the-limit",
     {"a.R": SMALL, "unix/u.R": lines(7)}, "1000", "", (0, 2, 7)),
    ("L21-unix-subdir-OVER-the-limit",
     {"a.R": SMALL, "unix/big.R": BIG}, "5", "", (1, "R/unix/big.R")),
    # R/windows/ is never collated on a Linux runner, and every job here runs
    # on ubuntu-latest. These two fixtures separate "both" from "runner OS".
    ("L22-windows-subdir-under-the-limit",
     {"a.R": SMALL, "windows/w.R": lines(6)}, "1000", "", (0, 2, 6)),
    ("L23-windows-subdir-OVER-the-limit",
     {"a.R": SMALL, "windows/big.R": BIG}, "5", "", (1, "R/windows/big.R")),
    ("L24-both-subdirs-and-top-level",
     {"a.R": SMALL, "unix/u.R": lines(4), "windows/w.R": lines(11)},
     "1000", "", (0, 3, 11)),
    # A package whose only code file sits in an OS subdirectory is checked,
    # not reported as "the limit checked nothing".
    ("L25-only-an-OS-subdir-file", {"unix/u.R": lines(5)}, "1000", "",
     (0, 1, 5)),
    # ---- the allowlist, inside a subdirectory -------------------------------
    # A runner-OS gate rejects this entry as stale, so the file has no way to
    # be exempted. That is the second surface of the same gap.
    ("L26-allowlist-exempts-a-windows-subdir-file",
     {"a.R": SMALL, "windows/big.R": BIG}, "5", "R/windows/big.R",
     (0, 2, 10)),
    ("L27-allowlist-exempts-a-unix-subdir-file",
     {"a.R": SMALL, "unix/big.R": BIG}, "5", "R/unix/big.R", (0, 2, 10)),
    ("L28-allowlist-stale-subdir-entry-fails",
     {"a.R": SMALL, "unix/u.R": SMALL}, "5", "R/unix/gone.R",
     (1, "These loc-allowlist entries name no file in R/")),
    # The subdirectory exists and holds code, but not this file.
    ("L29-allowlist-stale-windows-entry-fails",
     {"a.R": SMALL, "windows/w.R": SMALL}, "5", "R/windows/gone.R",
     (1, "These loc-allowlist entries name no file in R/")),
    ("L30-allowlist-live-and-stale-subdir-entries-together",
     {"a.R": SMALL, "unix/big.R": BIG}, "5", "R/unix/big.R\nR/unix/gone.R",
     (1, "R/unix/gone.R", "R/unix/big.R")),
    # ---- the two holes interacting ------------------------------------------
    ("L31-lowercase-dot-r-inside-a-subdir",
     {"a.R": SMALL, "windows/big.r": BIG}, "5", "", (1, "R/windows/big.r")),
    ("L32-subdir-non-code-extensions-ignored",
     {"a.R": SMALL, "unix/vig.Rmd": BIG, "unix/notes.txt": BIG,
      "windows/doc.Rd": BIG}, "5", "", (0, 1, 3)),
    ("L33-subdir-dotfiles-ignored",
     {"a.R": SMALL, "unix/.hidden.R": BIG}, "5", "", (0, 1, 3)),
    # R collates R/unix/ and R/windows/ and no other subdirectory. Verified
    # against R CMD INSTALL: helper_fn from R/helpers/h.R is not collated.
    ("L34-a-non-OS-subdir-is-ignored",
     {"a.R": SMALL, "helpers/big.R": BIG}, "5", "", (0, 1, 3)),
    ("L35-no-recursion-below-the-OS-subdir",
     {"a.R": SMALL, "unix/deeper/big.R": BIG}, "5", "", (0, 1, 3)),
    # An empty OS subdirectory must not turn into a phantom entry.
    ("L36-empty-OS-subdirs-are-harmless",
     {"a.R": SMALL}, "1000", "", (0, 1, 3),
     ("R/unix", "R/windows")),
]


def unpack(fx):
    """Give every fixture six fields, so extra_dirs can stay optional."""
    return fx if len(fx) == 6 else fx + ((),)


def check(want, p):
    # (exit, n_files, max_found) when the second field is a count.
    if len(want) == 3 and isinstance(want[1], int):
        e, n, mx = want
        gn, gmx = parse(p)
        return (p.returncode == e and gn == n and gmx == mx,
                "exit=%s n=%s max=%s" % (p.returncode, gn, gmx))
    # (exit, must_appear[, must_not_appear]). The third field is what proves
    # setdiff(allowlist, files) in the other direction: a live entry alongside
    # a stale one must not itself be reported.
    e, sub = want[0], want[1]
    absent = want[2] if len(want) == 3 else None
    got = (p.stderr or "") + (p.stdout or "")
    ok = p.returncode == e and sub in got and (absent is None or
                                               absent not in got)
    desc = "exit=%s substr=%s" % (p.returncode, sub in got)
    if absent is not None:
        desc += " absent=%s" % (absent not in got)
    return (ok, desc)


def main():
    materialise_old()
    new = extract_step(NEW_TEMPLATE)
    old = extract_step(OLD_TEMPLATE)
    assert new != old, "old and new step bodies are identical"
    print("OLD step body from %s (%s)" % (OLD_TEMPLATE, OLD_REF))
    print("NEW step body from %s" % NEW_TEMPLATE)
    print("=" * 78)
    print("%-46s %-28s %s" % ("fixture", "NEW (expected)", "OLD (same input)"))
    print("=" * 78)
    bad = 0
    for name, files, max_loc, allow, want, extra in map(unpack, FIXTURES):
        d = build(name, files, extra)
        pn = run(new, d, max_loc, allow)
        ok, desc = check(want, pn)
        d2 = build(name + "-old", files, extra)
        po = run(old, d2, max_loc, allow)
        on, omx = parse(po)
        odesc = "exit=%s n=%s max=%s" % (po.returncode, on, omx)
        bad += 0 if ok else 1
        print("%-46s %-28s %s%s"
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
