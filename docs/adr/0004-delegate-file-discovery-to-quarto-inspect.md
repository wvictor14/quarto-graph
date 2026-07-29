# File discovery delegates to `quarto inspect`, with an exclude-only fallback

`discover_paths` (`core.py`) only ever excluded dot/underscore-prefixed
paths. Real Quarto also excludes `README.md`/`README.qmd` and
`CLAUDE.md`/`AGENTS.md` by default, and lets a project fully override its
render scope via `project: render:` (a glob list with `!`-prefixed
negation). Left alone, a page Quarto never renders could still become a
graph node with an empty URL, and a user's `render:` excludes were silently
ignored, polluting the registry and backlink map with pages that don't
really exist in the rendered site.

Considered reimplementing Quarto's `render:` resolution ourselves:
sequential glob matching with negation, plus the four hardcoded default
exclusions. Rejected: this project already got burned once guessing at a
Quarto convention instead of asking Quarto directly (see
`0001-non-destructive-render-time-resolution.md`, the vault-era 404 bug from
guessing an output-path convention). A hand-rolled matcher is exactly that
same kind of guess, and every future Quarto release is a chance for it to
silently drift out of sync.

Considered always shelling out to `quarto inspect` unconditionally, whose
`files.input` is confirmed (empirically, against Quarto 1.9.37) to be
Quarto's own fully-resolved render list: `render:`, negation, and all four
default exclusions, exactly. Rejected as the *only* mechanism: `quarto
inspect` refuses to run against a directory with no `_quarto.yml`/
`_quarto.yaml` ("... is not a Quarto project"), and `quarto-graph check`
must keep working standalone against a plain folder of notes that was never
wrapped in a Quarto project, a real, plausible use case, not just a test
fixture.

Considered giving `check.py` and `prerender.py` two separate discovery
functions: `prerender.py` always has a real project (a pre-render hook
can't fire otherwise) so it could unconditionally use `quarto inspect`,
while `check.py` kept its own hand-rolled scan. Rejected: the two callers'
results must stay consistent with each other, and two independent
implementations only stay consistent by convention, not by construction.

Decided instead: one `discover_paths`, still called by both, branching on
whether `_quarto.yml`/`_quarto.yaml` exists (confirmed empirically that
even a bare file with no `project:` key, only quarto-graph's own
`quarto-graph:` block, is enough for Quarto to treat it as a real
project). If it exists, delegate entirely to `quarto inspect`. If not, fall
back to the original rglob scan, now also filtering the four default
filenames by hand (dot/underscore filtering was already there). Subprocess
failures in the `quarto inspect` branch are left to propagate unhandled.
`prerender.py` only ever calls this from inside an already-running `quarto
render`/`preview`, so if `quarto inspect` fails there, the render itself is
already broken for the same reason; wrapping the error adds nothing. This
also means the `test` CI job now needs Quarto installed (previously only
`publish-docs` did). Accepted, since a hand-mocked `quarto inspect` JSON
shape in tests would reintroduce the exact guessing this decision exists to
avoid.

A related but separate addition landed alongside this: `quarto-graph:
exclude:` in `_quarto.yml`, quarto-graph's own opt-out list, layered on top
of whichever branch produced the base file list. This is deliberately not
Quarto's `render:` glob spec (no negation, no extglob). It's a short
exclude-only list, matched by a trailing-`/` directory prefix or plain
`fnmatch`. Its exclusion is a full opt-out: an excluded page is invisible
to the whole wikilink system, not just hidden from the graph widget's
visualization. A `[[wikilink]]` pointing at it comes back unresolved, the
same as a typo. Page-level frontmatter override (mirroring the existing
`sidebar:` cascade in `page_sidebar_config`) was considered and deferred.
Project-level is the simpler starting scope, and the cascade pattern is
cheap to extend to later if a real need shows up.
