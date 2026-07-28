# Ambiguous wikilink targets disambiguate by ancestor-qualified path, not unique titles

Real Quarto projects put an `index.qmd` in every slug-named folder, so a
title-less `index.qmd`'s only default name (its filename stem) was already
excluded from the registry — every folder's index page would otherwise
collide on the literal word "index". The registry's `title:` fallback never
got the same treatment, though: it fell back to `path.stem`, so two
title-less `index.qmd` pages in different folders both registered under
`"index"` and collided there too, with no way to disambiguate.

Considered requiring every page to have a globally-unique `title:` or
`also-known-as:` — the existing escape hatch — but that's manual, easy to
forget, and doesn't scale to a project with many folders.

Considered resolving `index.qmd` only by its containing folder's name and
stopping there (an index-only patch) — but a plain stem or `title:` clash
between two *non*-index pages has the exact same shape of problem and no
better an answer today than "give one an `also-known-as:`".

Decided instead to adopt Foam's model generally: every page's folder-path
identifier (its stem, or its folder's name for an index page) and its
`title:` also register progressively longer ancestor-qualified forms
(`[[api]]` → `[[docs/api]]` → `[[project/docs/api]]`). An ambiguous bare name
still warns and keeps the first page registered, unchanged — but the other
page is now reachable by qualifying it with enough of its own path to be
unique, with no `also-known-as:` bookkeeping required. `index.qmd` also
resolves by bare folder name automatically (folder-note style, matching
Obsidian's folder-note plugins and Quartz), plus its literal `folder/index`
spelling for anyone who'd rather write that out. See AGENTS.md's
**Folder-path identifier** and **Qualified target** entries.
