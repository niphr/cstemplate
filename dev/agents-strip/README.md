# Test for the step that keeps agent instructions off the site

`run.sh` tests the step "Keep agent instructions off the published site" in
`../../.github/workflows/r-package.yml`. That step MUST remove `CLAUDE.*`, `PROJECT.*` and
`AGENTS.*` from the built pkgdown site.

## Run it

```bash
bash dev/agents-strip/run.sh                    # fake site with AGENTS pages
bash dev/agents-strip/run.sh --no-agents        # fake site without AGENTS pages
bash dev/agents-strip/run.sh path/to/other.yml  # test a different workflow file
```

Each run prints `STEP_EXIT`, `CLAUDE_LEFT` and `AGENTS_LEFT`. A count is the sum of the files
left under `docs/`, the lines left in `sitemap.xml` and the entries left in `search.json`. The
script exits 1 in these cases:

- the step exits non-zero
- either count is above 0
- the step removes `index.html`, its sitemap line or its search entry

Both modes MUST exit 0 against the shipped workflow. `--no-agents` proves that `AGENTS.md`
stays optional for a caller package.

The script needs `bash`, `awk`, `sed`, `find`, `python3` and `jq`. The step itself calls
`python3`. The Ubuntu 24.04 runner image lists Bash 5.2, Python 3.12 and jq 1.7 in its readme.
`awk`, `sed` and `find` are part of base Ubuntu.

## How it works

**The script reads the step from the YAML on every run.** It holds no copy of the step, so the
two cannot drift. `awk` extracts the `run: |` block, because PyYAML is not installed on every
machine that runs this. The extraction removes CR characters, so a Windows checkout works. On
2026-10-12 the extracted text matched `yaml::read_yaml()` byte for byte, after CR removal.

**The fake site uses the format that pkgdown 2.1.3 writes.** `build_sitemap()` writes one
`<url><loc>` line per page. `search.json` is a JSON array of objects with 8 fields. The published
`csdb` site also carried `{"path": []}` objects: 36 of 274 entries on 2026-10-12. The fixture
includes one.

**The `index.html` search entry names `AGENTS.md` in its text.** The step filters on the `path`
field, so that entry MUST survive. A filter on the text would remove it, and the script would
exit 1.
