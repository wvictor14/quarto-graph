# quarto-graph

Adds Obsidian-style wikilink functionality, linking, backlinks, and a graph
visualization, directly to a normal Quarto project's own pages. It is not a
vault-to-website converter: it does not import, transform, or mirror an
Obsidian vault, does not convert Obsidian callouts, and never writes or
rewrites files anywhere in the consuming project.

## Dev environment

Use `uv sync` to set up the Python environment. Never hand-roll a `venv/` +
`pip install`; the repo already has `pyproject.toml` + `uv.lock` for this.

## Prose

When writing documentation, use the skill /prose-style to ensure AI-slop and 
em dashes don't make it through.

## Language

**Wikilink**:
The `[[Target]]` (optionally `[[Target#Heading|display text]]`) syntax,
resolved at render time against every page already in the project into a
real link to that page's own source path. Resolution never rewrites the
`.qmd` file it appears in. The bracket syntax stays in the source forever.
_Avoid_: vault link (there is no vault).

**Also-known-as**:
A page's own frontmatter key (`also-known-as:`) listing extra free-text
names its wikilinks can be reached by, in addition to its filename stem.
Deliberately a separate key from Quarto's native `aliases:`. That key's
values are URLs Quarto turns into redirect stubs; an also-known-as value is
a human-readable alternate name, not a URL, and the two must never be
conflated.
_Avoid_: alias (ambiguous with Quarto's own `aliases:` key), wikilink alias.

**Registry**:
The pre-render pass's in-memory map from every page's title, folder-path
identifier, qualified target, and also-known-as name to that page, plus the
backlink map (which pages point at which). Built once per render, before any
single page renders, since a per-page Lua filter can't discover the rest of
the project on its own. Handed to the Lua filter as a side-channel file, not
embedded in any page.

**Folder-path identifier**:
A page's name as derived from its own project-relative path, not its
`title:`. Same as its filename stem, except for an `index.qmd`/`index.md`,
where it's the name of the *containing folder* instead. A page at
`page1/index.qmd` is a folder note, the same way Obsidian's folder-note
plugins and Quartz treat it, so `[[page1]]` resolves to it directly, and the
bare word `index` is never itself a usable target. The one exception is the
project's own top-level `index.qmd`, which has no containing folder to fold
into and is unique by construction.

**Qualified target**:
A wikilink target prefixed with one or more ancestor folder names
(`docs/api`, `project/docs/api`), used to disambiguate a folder-path
identifier or `title:` that collides between two pages, most commonly two
folders' `index.qmd` sharing a folder name. Resolves the same way Foam
disambiguates two same-named notes in different folders: by qualifying the
name with enough of its own path to be unique. `also-known-as:` names are
never qualified this way, since that tier is already a deliberately-chosen
unique name.

**Backlinks**:
The auto-appended "pages that link here" section on a page. Computed from
the registry and injected into the Pandoc AST by the Lua filter at that
page's own render time. Never written into the `.qmd` source.

**Graph widget / `graph.json`**:
The force-directed visualization (full-page view and per-page sidebar
mini-panel) reading `graph.json`: nodes are pages, edges are resolved
wikilinks and internal Markdown links (`[text](other.qmd)`) between project
pages; an external URL, asset link, or non-matching path is left alone,
not an edge. Node URLs in `graph.json` must be the actual final rendered
paths (the browser navigates to them directly, with no help from Quarto's
own link rewriting), so they're assembled from each page's own real output
path after that page renders, never computed independently by this
project.
_Avoid_: pretty URL, output path convention (this project does not compute
either; that was the old vault pipeline's job, and its bug source).

**Shortcode**:
How you opt into the full graph page, e.g. `{{< quarto-graph-full >}}`
placed on any page you choose. The extension never auto-generates a page
into your project; if you want one, you place the shortcode yourself.

