#!/usr/bin/env python3
"""Mutation proofs. Break one thing in the shipped step, name the fixture that goes red.

A mutation that changes no fixture verdict pins nothing, and is reported as
UNPROVEN rather than quietly dropped.
"""
import importlib.util
import io
import os
import shutil
import sys
import contextlib

spec = importlib.util.spec_from_file_location("h2", "/tmp/phase6b/harness2.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

BODY = h.extract_step()

RM_LINE = "rm -f docs/CLAUDE.html docs/CLAUDE.md docs/PROJECT.html docs/PROJECT.md\n"
TEST_LINE = "test -f docs/CLAUDE.html\n"
SITEMAP_ASSERT = """\
if grep -qE 'CLAUDE\\.|PROJECT\\.' docs/sitemap.xml; then
  echo "docs/sitemap.xml still lists an agent instructions page:"
  grep -nE 'CLAUDE\\.|PROJECT\\.' docs/sitemap.xml
  exit 1
fi
"""
SEARCH_ASSERT = """\
if [ -n "$agent_indexed" ]; then
  echo "docs/search.json still indexes an agent instructions page:"
  echo "$agent_indexed"
  exit 1
fi
"""
FIND_BLOCK = """\
# This assertion catches any further extension that pkgdown emits.
left=$(find docs \\( -name 'CLAUDE.*' -o -name 'PROJECT.*' \\) -print)
if [ -n "$left" ]; then
  echo "These agent instruction files survive under docs/:"
  echo "$left"
  exit 1
fi
"""
PY_WRITE = '    with open(P, "w") as fh:\n        json.dump(kept, fh)\n'
PY_PREDICATE = (
    '    url = str(entry.get("path") or "").split("?")[0].split("#")[0]\n'
    '    return bool(AGENT.match(url.rsplit("/", 1)[-1]))\n'
)
PY_EXISTS = "if os.path.exists(P):\n"
PY_CLOSE = "\nPY\n)\n"

PY_START = "agent_indexed=$(python3 - <<'PY'\n"

for name, frag in [("RM_LINE", RM_LINE), ("TEST_LINE", TEST_LINE),
                   ("SITEMAP_ASSERT", SITEMAP_ASSERT), ("SEARCH_ASSERT", SEARCH_ASSERT),
                   ("FIND_BLOCK", FIND_BLOCK), ("PY_WRITE", PY_WRITE),
                   ("PY_PREDICATE", PY_PREDICATE), ("PY_EXISTS", PY_EXISTS),
                   ("PY_CLOSE", PY_CLOSE), ("PY_START", PY_START)]:
    assert frag in BODY, "%s not found in the shipped step body" % name

i0 = BODY.index(PY_START)
i1 = BODY.index(PY_CLOSE) + len(PY_CLOSE)
PY_WHOLE = BODY[i0:i1]

MUTATIONS = [
    ("M1  remove docs/CLAUDE.md from the rm line",
     BODY.replace(RM_LINE, "rm -f docs/CLAUDE.html docs/PROJECT.html docs/PROJECT.md\n")),
    ("M2  remove docs/PROJECT.md from the rm line",
     BODY.replace(RM_LINE, "rm -f docs/CLAUDE.html docs/CLAUDE.md docs/PROJECT.html\n")),
    ("M3  remove the `test -f docs/CLAUDE.html` canary",
     BODY.replace(TEST_LINE, "")),
    ("M4  sitemap assertion written as a bare `! grep`, mid-script",
     BODY.replace(SITEMAP_ASSERT,
                  "! grep -qE 'CLAUDE\\.|PROJECT\\.' docs/sitemap.xml\n")),
    ("M5  remove the final find assertion",
     BODY.replace(FIND_BLOCK, "")),
    ("M6  purge computes the kept list but never writes it",
     BODY.replace(PY_WRITE, "    pass\n")),
    ("M7  predicate matches the entry TEXT instead of its path",
     BODY.replace(PY_PREDICATE,
                  '    return bool(re.search(r"(CLAUDE|PROJECT)\\.", json.dumps(entry)))\n')),
    ("M8  remove the `os.path.exists` guard on docs/search.json",
     BODY.replace(PY_EXISTS, "if True:\n")),
    ("M9  swallow the python exit status with `|| true`",
     BODY.replace(PY_CLOSE, "\nPY\n) || true\n")),
    ("M10 remove the search.json block AND its assertion",
     BODY.replace(PY_WHOLE, "").replace(SEARCH_ASSERT, "")),
]


def verdicts(body):
    """Run every fixture quietly, return {name: (got, want, ok)}."""
    out = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        name, want, checks = h.REAL_FIXTURE
        d = h.build_real(os.path.join("mut", name))
        ok = h.one(body, name, d, want, checks, verbose=False)
        out[name] = ok
        for name, files, sitemap, search, want, checks in h.FIXTURES:
            d = h.build(os.path.join("mut", name), files, sitemap, search)
            out[name] = h.one(body, name, d, want, checks, verbose=False)
    return out


base = verdicts(BODY)
print("### BASELINE, shipped step body")
for k, ok in base.items():
    print("  %-38s %s" % (k, "PASS" if ok else "FAIL"))
assert all(base.values()), "baseline is not green, so no mutation proof is valid"
print()

unproven = []
for label, body in MUTATIONS:
    assert body != BODY, "%s changed nothing in the step body" % label
    v = verdicts(body)
    red = [k for k in v if not v[k]]
    print("### %s" % label)
    if not red:
        print("  UNPROVEN: no fixture changed verdict")
        unproven.append(label)
    else:
        print("  RED-FIXTURES: %s" % ", ".join(sorted(red)))
    print()

shutil.rmtree(os.path.join(h.ROOT, "mut"), ignore_errors=True)
print("MUTATIONS WITH NO RED FIXTURE: %d of %d" % (len(unproven), len(MUTATIONS)))
for u in unproven:
    print("  UNPROVEN: %s" % u)
sys.exit(0)
