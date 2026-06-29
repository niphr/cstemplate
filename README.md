# cstemplate

Shared **pkgdown house style** for the cs* package family — Spectral + Source Sans 3
typography, the navy/coral palette, a `cs* family` navbar switcher, and a common
footer. Build it once; every cs* site inherits it.

This package only ships theme assets — it is infrastructure, not a user-facing
package, and is intentionally left out of the `cs* family` switcher and the
registry. (For the real output-styling package, see
[csstyle](https://niphr.github.io/csstyle/).)

## Use it in a package

1. Declare `cstemplate` as a website dependency in the package's `DESCRIPTION`,
   as an **inline GitHub ref** (the CI installs `Config/Needs/website` entries
   directly with pak, so a bare package name — with or without a `Remotes:`
   line — will *not* resolve):

   ```
   Config/Needs/website: niphr/cstemplate
   ```

2. Point the package's `_pkgdown.yml` at the template:

   ```yaml
   template:
     package: cstemplate

   # keep your own url + reference: / articles: groups below
   ```

3. Rebuild: `pkgdown::build_site()`.

That's it — fonts, colours, navbar, and footer all come from here. Per-package
overrides still work: anything you set in your own `_pkgdown.yml` wins.

## What's inside

```
inst/pkgdown/
  _pkgdown.yml              navbar + footer structure, fonts, palette + Bootstrap
                            variable overrides (template > bslib)
  extra.scss                custom CSS rules, added after Bootstrap
```

> Note: a pkgdown *template* package ships its custom CSS via
> `inst/pkgdown/extra.scss` (the "rules" layer). Files under `inst/pkgdown/BS5/`
> are **not** sourced into consuming sites, so all component styling lives in
> `extra.scss`; Sass-variable overrides go in `template > bslib` in `_pkgdown.yml`.

## Editing the look

- **Colours / fonts / Bootstrap variables** → `_pkgdown.yml` (`template > bslib`).
- **Component styling** (hero, code blocks, reference index, footer strip) →
  `extra.scss` (the `$cs-*` tokens are defined at its top).
- **Family menu / footer links** → `_pkgdown.yml` components.

The umbrella registry site (niphr.github.io) is a Jekyll site; it reuses the same
palette and fonts via its own stylesheet so the two stay visually in sync.
