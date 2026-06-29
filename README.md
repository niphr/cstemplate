# cstemplate

Shared **pkgdown house style** for the cs* package family — Spectral + Source Sans 3
typography, the navy/coral palette, a `cs* family` navbar switcher, and a common
footer. Build it once; every cs* site inherits it.

This package only ships theme assets — it is infrastructure, not a user-facing
package, and is intentionally left out of the `cs* family` switcher and the
registry. (For the real output-styling package, see
[csstyle](https://niphr.github.io/csstyle/).)

## Use it in a package

1. Add `cstemplate` to the package's website dependencies:

   ```r
   usethis::use_dev_package("cstemplate", type = "Config/Needs/website",
                            remote = "niphr/cstemplate")
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
  _pkgdown.yml              navbar + footer structure, fonts, palette (bslib)
  BS5/_variables.scss       Sass variables — imported before Bootstrap
  BS5/_rules.scss           custom CSS — imported after Bootstrap
```

## Editing the look

- **Colours / fonts** → `_pkgdown.yml` (`template > bslib`) and the `$cs-*`
  tokens at the top of `BS5/_variables.scss`.
- **Component styling** (hero, code blocks, reference index, footer strip) →
  `BS5/_rules.scss`.
- **Family menu / footer links** → `_pkgdown.yml` components.

The umbrella registry site (niphr.github.io) is a Jekyll site; it reuses the same
palette and fonts via its own stylesheet so the two stay visually in sync.
