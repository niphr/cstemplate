#!/usr/bin/env bash
# Run the shipped "Keep agent instructions off the published site" step
# against a fake pkgdown docs/ directory, and count what it left behind.
#
# Usage: run.sh [--no-agents] [workflow]
#
#   workflow     path to the workflow YAML. Default: the r-package.yml two
#                directories above this script.
#   --no-agents  build the fake site without any AGENTS file or entry.
#
# Prints CLAUDE_LEFT <n> and AGENTS_LEFT <n>. Exits 1 when the step failed,
# when either count is above 0, or when the step removed index.html, its
# sitemap line or its search entry. Needs bash, awk, sed, find, python3 and jq.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
agents=1
if [ "${1:-}" = "--no-agents" ]; then
  agents=0
  shift
fi
workflow=${1:-$here/../../.github/workflows/r-package.yml}
step_name="Keep agent instructions off the published site"

if [ ! -f "$workflow" ]; then
  echo "No workflow file at $workflow"
  exit 2
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Extract the literal block under `run: |` of the named step. YAML strips the
# indentation of the first non-blank block line from every line, and the
# block ends at the first non-blank line indented no deeper than `run:`.
# A CR is removed from every line, because a Windows checkout has CRLF.
awk -v name="$step_name" '
  { sub(/\r$/, "") }
  $0 ~ "^[[:space:]]*- name: " name "[[:space:]]*$" { nsteps++ }
  !found {
    if ($0 ~ "^[[:space:]]*- name: " name "[[:space:]]*$") {
      found = 1
      match($0, /^[[:space:]]*/)
      key = RLENGTH + 2
    }
    next
  }
  !inrun {
    if ($0 ~ /^[[:space:]]*$/) next
    match($0, /^[[:space:]]*/)
    if (RLENGTH < key) { found = 0; next }
    if (RLENGTH == key && $0 ~ /^[[:space:]]*run: \|[[:space:]]*$/) {
      inrun = 1
      nruns++
    }
    next
  }
  {
    if ($0 ~ /^[[:space:]]*$/) { blank = blank "\n"; next }
    match($0, /^[[:space:]]*/)
    if (RLENGTH <= key) { inrun = 0; found = 0; next }
    if (!block) block = RLENGTH
    if (RLENGTH < block) { print "bad indentation in the run block" > "/dev/stderr"; exit 3 }
    printf "%s%s\n", blank, substr($0, block + 1)
    blank = ""
  }
  END {
    if (nsteps != 1 || nruns != 1) {
      printf "expected 1 step named \"%s\" with 1 run: | block, found %d steps and %d blocks\n", \
        name, nsteps, nruns > "/dev/stderr"
      exit 3
    }
  }
' "$workflow" > "$work/step.sh"

# The fake site, in the shape pkgdown 2.1.3 writes. build_sitemap() writes
# one <url><loc> line per page. build_search_index() writes a JSON array of
# objects with these 8 fields, and pkgdown also emits {"path":[]} objects.
# The index.html entry names AGENTS.md in its text, which the step MUST keep.
docs="$work/docs"
mkdir -p "$docs"
U="https://example.org/pkg/"
echo "<html>index</html>" > "$docs/index.html"
echo "<html>CLAUDE</html>" > "$docs/CLAUDE.html"
echo "# CLAUDE" > "$docs/CLAUDE.md"
{
  echo "<urlset xmlns = 'http://www.sitemaps.org/schemas/sitemap/0.9'>"
  if [ "$agents" = 1 ]; then echo "<url><loc>${U}AGENTS.html</loc></url>"; fi
  echo "<url><loc>${U}CLAUDE.html</loc></url>"
  echo "<url><loc>${U}index.html</loc></url>"
  echo "</urlset>"
} > "$docs/sitemap.xml"

entry() {
  printf '{"path":"%s%s","id":"%s","dir":"","previous_headings":"","what":"%s","title":"%s","text":"%s","code":""}' \
    "$U" "$1" "$2" "$3" "$4" "$5"
}
{
  printf '['
  if [ "$agents" = 1 ]; then
    echo "<html>AGENTS</html>" > "$docs/AGENTS.html"
    echo "# AGENTS" > "$docs/AGENTS.md"
    entry AGENTS.html project-overview "Project Overview" AGENTS.md "agent guidance"
    printf ','
    entry AGENTS.html commands "Commands" AGENTS.md "build commands"
    printf ','
  fi
  printf '{"path":[]},'
  entry CLAUDE.html overview "Overview" CLAUDE.md "agent guidance"
  printf ','
  entry index.html pkg "pkg" pkg "See AGENTS.md for agent guidance."
  printf ']\n'
} > "$docs/search.json"
jq -e 'type == "array"' "$docs/search.json" > /dev/null

if (cd "$work" && bash step.sh); then
  step_rc=0
else
  step_rc=$?
fi

for f in sitemap.xml search.json; do
  if [ ! -f "$docs/$f" ]; then
    echo "STEP_EXIT $step_rc"
    echo "docs/$f was removed"
    exit 1
  fi
done

# Count by name, the way the step decides: a file name, a sitemap line, or the
# basename of a string `path` field.
count_left() {
  local stem=$1 files lines entries
  files=$(find "$docs" -name "$stem.*" | wc -l)
  lines=$(grep -c "/$stem\." "$docs/sitemap.xml" || true)
  entries=$(jq --arg s "$stem." \
    '[.[] | select((.path | type) == "string")
          | select(.path | split("/") | last | startswith($s))] | length' \
    "$docs/search.json")
  echo $((files + lines + entries))
}

fail=0
claude_left=$(count_left CLAUDE)
agents_left=$(count_left AGENTS)
echo "STEP_EXIT $step_rc"
echo "CLAUDE_LEFT $claude_left"
echo "AGENTS_LEFT $agents_left"

if [ "$step_rc" -ne 0 ]; then fail=1; fi
if [ "$claude_left" -gt 0 ]; then fail=1; fi
if [ "$agents_left" -gt 0 ]; then fail=1; fi
if [ ! -f "$docs/index.html" ]; then
  echo "index.html was removed"
  fail=1
fi
if ! grep -q "<url><loc>${U}index.html</loc></url>" "$docs/sitemap.xml"; then
  echo "the index.html sitemap line was removed"
  fail=1
fi
kept=$(jq --arg p "${U}index.html" '[.[] | select(.path == $p)] | length' "$docs/search.json")
if [ "$kept" -ne 1 ]; then
  echo "expected 1 index.html search entry, found $kept"
  fail=1
fi

exit "$fail"
