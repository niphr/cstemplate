# cs* pkgdown + hub design — hand-off (continue on Mac)

Goal: make every cs* package's pkgdown site (and the niphr.github.io hub) match the
Claude Design mockups (hero landing page, polished articles/reference, dark code
blocks that are READABLE). Richard has the mockup images — they are the design target.

All package repos live in the GitHub `niphr` org. Clone what you need; everything
below is already pushed unless noted.

## Why move to the Mac
The previous session ran headless on Unraid: no browser to screenshot (Chrome
needs system libs, no root) and an OLD pandoc (2.9.2.1) that can't do a full
`pkgdown::build_site()` of the home (errors "pandoc error 23"). On the Mac you have
Chrome + a newer pandoc, so build locally and preview instantly instead of waiting
~10–12 min per CI deploy.

## STATUS as of hand-off (Richard takes over on Mac)
- Readable dark code is LIVE on csmaps (the big recurring bug — fixed, see gotcha #3).
- Article/reference "Reference"/"Article" eyebrows added to cstemplate (pushed).
- niphr.github.io hub restyle is now PUSHED.
- csmaps favicons committed (`csmaps/pkgdown/favicon/`) so CI won't regenerate.
- Full-bleed hero was REVERTED (broke CI once); retry locally with preview — the
  in-column hero is what's live now.
- NEXT: bespoke homes for the other 8 packages + per-package visuals; rebuild all 9
  so they pick up the latest cstemplate.
- NOT pushed (left as your WIP on the Unraid box): cs9's uncommitted vignettes/NEWS/
  CLAUDE.md + a .docx (and cs9 `stash@{0}`), csdb CRAN files. Clone-fresh on the Mac
  won't have these — grab them from Unraid if you need them.

## What's DONE (pushed, live)
- **`niphr/cstemplate`** — NEW pkgdown *template* package (the house style). This is
  the renamed thing: Claude Design called it `csstyle`, but `csstyle` is a real
  package, so the template was renamed to **cstemplate**.
- **All 9 packages wired** to it: each `_pkgdown.yml` has `template: package: cstemplate`,
  each DESCRIPTION has `Config/Needs/website: niphr/cstemplate`.
  Packages: cs9, csalert, csdata, csdb, csmaps, csstyle, cstidy, cstime, csutil.
- **csmaps is the flagship** and is GREEN + live (https://niphr.github.io/csmaps/):
  bespoke home (`csmaps/index.md`) with hero + "Geographic granularities" cards +
  a "Map gallery" of REAL rendered thumbnails (`csmaps/pkgdown/assets/gallery/*.png`)
  + an Install code box (sidebar component in `csmaps/_pkgdown.yml`).
- **`attrib/` deleted** (was unused).
- **Readable dark code FIX is live** (see gotcha #3 — this was the big recurring bug).

## What's NOT done / known issues
1. **The other 8 packages still need their bespoke homes** (hero + per-package
   "generated visuals" — e.g. csstyle palette swatches, cstime a week/calendar
   motif). They currently show a plain home. They also need a rebuild to pick up the
   latest cstemplate CSS (rerun their "Check and pkgdown" workflow, or push a commit).
2. **Full-bleed hero was reverted.** The mockup hero spans full width above the
   sidebar. The attempt used a `content-home.html` template override that COINCIDED
   with a CI build failure, so it was reverted to the in-column hero. Redo it ON THE
   MAC with local preview so you can see it before pushing. (The override mechanism
   itself works — template packages CAN provide `inst/pkgdown/BS5/templates/`.)
3. **niphr.github.io hub** — the restyled Jekyll hub is applied LOCALLY in
   `niphr.github.io/` (new `_config.yml`, `_layouts/default.html`,
   `assets/css/cs-hub.css`, merged `index.md`) but NOT pushed yet.
4. **cs9 CI is RED** for a pre-existing, unrelated reason: `R CMD check` WARNING
   "Undocumented code objects: 'TaskJob' 'run_task_sequentially_as_callr_bg_using_load_all'".
   Needs roxygen docs for those (cs9 dev work, not design). Its pkgdown job is gated
   behind the check so the site won't deploy until fixed.
5. **cs9 has a safety `stash@{0}`** holding Richard's uncommitted work (CLAUDE.md,
   NEWS.md, vignettes) that a rebase displaced — don't lose it.

## Local dev loop (on the Mac)
```r
# install the template locally first, then preview a package's home fast:
R CMD INSTALL --no-docs path/to/cstemplate
# in the package dir:
pkgdown::build_site()              # full (now works with a current pandoc)
# or fast home-only iteration:
p <- pkgdown::as_pkgdown("."); pkgdown::init_site(p); pkgdown::build_home(p)
# then open docs/index.html in Chrome (or pkgdown::preview_site())
```
Re-install cstemplate after every edit to its `inst/pkgdown/` files.

## GOTCHAS (this is the valuable part — don't relearn blind)
1. **Template dep declaration:** consuming packages must use
   `Config/Needs/website: niphr/cstemplate` (an INLINE GitHub ref). A bare name
   `cstemplate` + a `Remotes:` line does NOT work — pak feeds `Config/Needs/website`
   entries as bare refs and ignores `Remotes` for them ("Can't find package cstemplate").
2. **Where template CSS lives:** a pkgdown *template package* ships custom CSS in
   `inst/pkgdown/extra.scss` (the "rules" layer). Files under `inst/pkgdown/BS5/_rules.scss`
   are NOT sourced into consuming sites (Claude Design put them there — that's why
   nothing was styled at first). Bootstrap/bslib variable overrides go in
   `template > bslib` in `cstemplate/inst/pkgdown/_pkgdown.yml`.
3. **Dark code readability (the recurring "can't read" bug):** pkgdown ships its own
   highlight CSS that colours tokens for a LIGHT bg, e.g. `code span.va{color:#111111}`
   (variable names = black) — invisible on our dark code block, and it out-specifies
   loose rules. Fix (already in `cstemplate/inst/pkgdown/extra.scss`): a
   high-specificity catch-all `pre code span { color:#e7ecf1 !important }` plus accent
   classes (`.fu` coral, `.st` green, etc.), all `!important`, and
   `pre code a { color: inherit !important }` so downlit's function/dataset LINKS take
   their token colour instead of the navy page-link colour. Keep this pattern.
4. **pkgdown injects a `.page-header`** (logo + h1) into the home; the hero CSS hides
   the duplicate logo via `.cs-hero .page-header .logo { display:none }`.
5. **pkgdown renders root `.md` files** as home pages — it tried to render `CLAUDE.md`.
   Wasn't the failure here, but be aware.
6. **Palette:** navy `#1e2c3a`, coral `#e0533c`, warm bg `#fbfaf7`, border `#ece8e1`.
   Fonts: Spectral (headings), Source Sans 3 (body), JetBrains Mono (code/labels).
7. **cstemplate is infra** — keep it OUT of the cs* family navbar/registry; but
   `csstyle` (the real output-styling package) STAYS in them.

## Memory
A durable note was saved at the Unraid session memory:
`cstemplate-website-dep.md` (gotcha #1). Consider re-saving #2 and #3 on the Mac.
