#!/usr/bin/env python3
"""Run the shipped strip step against fixture docs/ directories.

The step body is read from the YAML that will be committed, via yaml.safe_load,
so the text under test is the text that ships.

Fixture F8 is a real pkgdown 2.2.0 site, built from a probe package that carries
sentinel strings in CLAUDE.md and PROJECT.md. Every other fixture is synthetic
and targets one branch.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap

import yaml

TEMPLATE = "/home/raw996/niphr/cstemplate/.github/workflows/r-package.yml"
STEP_NAME = "Keep agent instructions off the published site"
ROOT = "/tmp/phase6b/fx"
REAL_DOCS = "/tmp/pkgdownprobe/probepkg/docs"
SENTINELS = [
    "ZQXWCLAUDESENTINEL",
    "ZQXWCLAUDEHEADINGSENTINEL",
    "ZQXWPROJECTSENTINEL",
    "ZQXWPROJECTHEADINGSENTINEL",
]

AGENT = "# CLAUDE.md\n\nThis file provides guidance to Claude Code.\n"

SITEMAP_ONE_LINE = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/pkg/index.html</loc></url>
<url><loc>https://example.com/pkg/CLAUDE.html</loc></url>
<url><loc>https://example.com/pkg/reference/index.html</loc></url>
</urlset>
"""

SITEMAP_WITH_PROJECT = SITEMAP_ONE_LINE.replace(
    "<url><loc>https://example.com/pkg/CLAUDE.html</loc></url>",
    "<url><loc>https://example.com/pkg/PROJECT.html</loc></url>\n"
    "<url><loc>https://example.com/pkg/CLAUDE.html</loc></url>",
)

SITEMAP_NO_AGENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/pkg/index.html</loc></url>
<url><loc>https://example.com/pkg/reference/index.html</loc></url>
</urlset>
"""

# pkgdown writes one <url><loc>..</loc></url> per line. A pretty-printed
# sitemap splits that across three lines, which the sed address cannot match.
SITEMAP_MULTILINE = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url>
  <loc>https://example.com/pkg/CLAUDE.html</loc>
</url>
<url><loc>https://example.com/pkg/index.html</loc></url>
</urlset>
"""


def entry(path, what, text):
    return {"path": path, "id": None, "dir": "", "previous_headings": "",
            "what": what, "title": what, "text": text, "code": ""}


U = "https://example.com/pkg/"

SEARCH_WITH_AGENT = json.dumps([
    entry(U + "index.html", "probepkg", "An ordinary home page."),
    entry(U + "CLAUDE.html", "CLAUDE.md", "file provides guidance Claude Code"),
    entry(U + "CLAUDE.html", "Licensing", "package MIT + file LICENSE"),
    entry(U + "PROJECT.html", "PROJECT.md", "Project notes agents"),
    entry(U + "reference/probe_one.html", "probe_one", "Returns one."),
])

SEARCH_NO_AGENT = json.dumps([
    entry(U + "index.html", "probepkg", "An ordinary home page."),
    entry(U + "reference/probe_one.html", "probe_one", "Returns one."),
])

# The cs9 case: a surviving page whose TEXT names CLAUDE.md. It MUST be kept.
SEARCH_TEXT_MENTIONS = json.dumps([
    entry(U + "index.html", "probepkg", "An ordinary home page."),
    entry(U + "news/index.html", "Licensing",
          "CLAUDE.md now carries a Licensing section, so PROJECT.md ages loudly."),
    entry(U + "CLAUDE.html", "CLAUDE.md", "file provides guidance Claude Code"),
])

SEARCH_MALFORMED = '[{"path": "https://example.com/pkg/CLAUDE.html", "what": '
SEARCH_NOT_ARRAY = '{"path": "https://example.com/pkg/CLAUDE.html"}'
SEARCH_NON_OBJECT_ENTRY = '[1, 2, 3]'


def build(name, files, sitemap, search):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "docs"))
    for rel, content in files.items():
        full = os.path.join(d, "docs", rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
    if sitemap is not None:
        with open(os.path.join(d, "docs", "sitemap.xml"), "w") as fh:
            fh.write(sitemap)
    if search is not None:
        with open(os.path.join(d, "docs", "search.json"), "w") as fh:
            fh.write(search)
    return d


def build_real(name):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copytree(REAL_DOCS, os.path.join(d, "docs"))
    return d


def listing(d):
    out = []
    for root, dirs, names in os.walk(os.path.join(d, "docs")):
        for n in names:
            out.append(os.path.relpath(os.path.join(root, n), d))
    return sorted(f for f in out if not f.endswith("step.sh"))


def search_paths(d):
    p = os.path.join(d, "docs", "search.json")
    if not os.path.exists(p):
        return None
    return [e.get("path") for e in json.load(open(p))]


# ---- post-conditions -------------------------------------------------------

def pc_no_sentinel(d):
    """No file anywhere under docs/ may hold a sentinel."""
    hits = []
    for root, dirs, names in os.walk(os.path.join(d, "docs")):
        for n in names:
            f = os.path.join(root, n)
            try:
                body = open(f, "rb").read()
            except OSError:
                continue
            for s in SENTINELS:
                if s.encode() in body:
                    hits.append((os.path.relpath(f, d), s))
    return ("no file holds a sentinel", hits == [], hits)


def pc_real_search_kept(d):
    """The real site keeps every non-agent entry and loses every agent one."""
    paths = search_paths(d)
    agent = [p for p in paths if "/CLAUDE." in p or "/PROJECT." in p]
    return ("search.json: 7 entries left, 0 agent, was 11",
            len(paths) == 7 and agent == [], {"left": len(paths), "agent": agent})


def pc_search_unchanged(expected_json):
    def f(d):
        p = os.path.join(d, "docs", "search.json")
        got = json.load(open(p))
        want = json.loads(expected_json)
        return ("search.json byte content unchanged", got == want,
                {"n_got": len(got), "n_want": len(want)})
    return f


def pc_search_paths(expected):
    def f(d):
        got = search_paths(d)
        return ("search.json paths == %s" % expected, got == expected, got)
    return f


def pc_no_search_file(d):
    p = os.path.join(d, "docs", "search.json")
    return ("docs/search.json absent", not os.path.exists(p), os.path.exists(p))


def pc_search_untouched_bytes(original):
    def f(d):
        p = os.path.join(d, "docs", "search.json")
        got = open(p).read()
        return ("malformed search.json left untouched", got == original,
                repr(got[:60]))
    return f


# ---- fixtures --------------------------------------------------------------

BASE = {"CLAUDE.html": "<html>agent</html>", "CLAUDE.md": AGENT,
        "index.html": "<html>home</html>"}

FIXTURES = [
    ("F1-claude-html-md-sitemap", dict(BASE), SITEMAP_ONE_LINE, None, 0, []),
    ("F2-project-as-well",
     dict(BASE, **{"PROJECT.html": "<html>p</html>", "PROJECT.md": "# PROJECT.md\n"}),
     SITEMAP_WITH_PROJECT, None, 0, []),
    ("F3-no-project", dict(BASE), SITEMAP_ONE_LINE, None, 0, []),
    ("F4-no-claude-html", {"CLAUDE.md": AGENT, "index.html": "<html>h</html>"},
     SITEMAP_NO_AGENT, None, 1, []),
    ("F5-sitemap-entry-sed-misses", dict(BASE), SITEMAP_MULTILINE, None, 1, []),
    ("F6-claude-md-in-subdirectory",
     dict(BASE, **{"articles/CLAUDE.md": AGENT}), SITEMAP_ONE_LINE, None, 1, []),
    ("F7-future-extension-claude-txt",
     dict(BASE, **{"CLAUDE.txt": AGENT}), SITEMAP_ONE_LINE, None, 1, []),
    ("F9-search-json-with-agent-entries", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_WITH_AGENT, 0,
     [pc_search_paths([U + "index.html", U + "reference/probe_one.html"]),
      pc_no_sentinel]),
    ("F10-search-json-with-none", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_NO_AGENT, 0, [pc_search_unchanged(SEARCH_NO_AGENT)]),
    ("F11-search-json-absent", dict(BASE), SITEMAP_ONE_LINE, None, 0,
     [pc_no_search_file]),
    ("F12-search-json-malformed", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_MALFORMED, 1, [pc_search_untouched_bytes(SEARCH_MALFORMED)]),
    ("F13-text-mentions-but-path-survives", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_TEXT_MENTIONS, 0,
     [pc_search_paths([U + "index.html", U + "news/index.html"])]),
    ("F14-search-json-not-an-array", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_NOT_ARRAY, 1, []),
    ("F15-search-json-non-object-entry", dict(BASE), SITEMAP_ONE_LINE,
     SEARCH_NON_OBJECT_ENTRY, 1, []),
]

REAL_FIXTURE = ("F8-real-pkgdown-2.2.0-site", 0,
                [pc_no_sentinel, pc_real_search_kept])


def extract_step(path=TEMPLATE):
    doc = yaml.safe_load(open(path))
    steps = doc["jobs"]["pkgdown"]["steps"]
    hits = [s for s in steps if s.get("name") == STEP_NAME]
    assert len(hits) == 1, "expected 1 step named %r, found %d" % (STEP_NAME, len(hits))
    return hits[0]["run"]


def run(body, d, shell=("bash", "--noprofile", "--norc", "-eo", "pipefail")):
    with open(os.path.join(d, "step.sh"), "w") as fh:
        fh.write(body)
    return subprocess.run(list(shell) + ["step.sh"], cwd=d,
                          capture_output=True, text=True)


def one(body, name, d, want, checks, verbose=True):
    before = listing(d)
    p = run(body, d)
    after = listing(d)
    ok = p.returncode == want
    results = []
    for c in checks:
        label, passed, detail = c(d)
        results.append((label, passed, detail))
        ok = ok and passed
    if verbose:
        print("### %s" % name)
        print("EXPECTED-EXIT: %d" % want)
        print("ACTUAL-EXIT:   %d   %s" % (p.returncode, "PASS" if ok else "FAIL"))
        if len(before) <= 12:
            print("BEFORE: %s" % ", ".join(before))
            print("AFTER:  %s" % ", ".join(after))
        else:
            print("BEFORE: %d files    AFTER: %d files" % (len(before), len(after)))
            gone = sorted(set(before) - set(after))
            print("REMOVED: %s" % ", ".join(gone))
        for label, passed, detail in results:
            print("POST: %-46s %s   %s"
                  % (label, "PASS" if passed else "FAIL", detail))
        if p.stdout.strip():
            print("STDOUT:")
            print(textwrap.indent(p.stdout.rstrip(), "  "))
        if p.stderr.strip():
            print("STDERR:")
            print(textwrap.indent(p.stderr.rstrip()[-700:], "  "))
        print()
    return ok


def all_fixtures(body, verbose=True):
    bad = 0
    name, want, checks = REAL_FIXTURE
    d = build_real(name)
    bad += 0 if one(body, name, d, want, checks, verbose) else 1
    for name, files, sitemap, search, want, checks in FIXTURES:
        d = build(name, files, sitemap, search)
        bad += 0 if one(body, name, d, want, checks, verbose) else 1
    return bad, len(FIXTURES) + 1


def main():
    body = extract_step()
    print("=" * 74)
    print("STEP BODY UNDER TEST, extracted from")
    print(TEMPLATE)
    print("with yaml.safe_load, jobs.pkgdown.steps[name == %r].run" % STEP_NAME)
    print("=" * 74)
    print(body)
    print("=" * 74)
    print()
    bad, total = all_fixtures(body)
    print("=" * 74)
    print("FIXTURE FAILURES: %d of %d" % (bad, total))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
