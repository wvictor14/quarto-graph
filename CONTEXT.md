# quarto-graph

Quarto extension rendering an Obsidian-style link graph (full-page view and
per-page sidebar mini-panel) from a project's resolved wikilinks and
Markdown links.

## Language

**Root** (of a widget instance):
The page a depth-limited `{{< quarto-graph-full >}}` widget is centered on.
Given via a `root=` kwarg identifying a page by wikilink-style name
(title / alias / filename-stem, case-insensitive, via the existing
registry) or, failing that, a literal `rel` source path. Defaults to the
page the shortcode is embedded on when `depth` is set without an explicit
`root`.
_Avoid_: Center, focus (focus already names the highlighted/current node in
graph.js's rendering options — a rendering detail, not this config concept)

**Depth** (of a widget instance):
How many link-hops out from a widget's `root` to include as visible nodes.
Unset means the widget shows the whole project graph. This is a
per-shortcode-call param, not a project-wide default.

**Expandable** (widget instance):
Whether a `{{< quarto-graph-full >}}` instance shows a button that expands
it to a fullscreen overlay. Opt-in via `expandable="true"`; off by default.
Distinct from the sidebar mini-panel's own always-on expand-to-modal
button, which predates this param and isn't controlled by it.

**Sidebar config** (`quarto-graph: sidebar:` in `_quarto.yml`/frontmatter):
`{enabled: bool, depth: int}`, or the bare bool shorthand (`sidebar: true`
== `{enabled: true, depth: 1}`). Cascades project default → page override
at the field level: an override naming only one field (e.g. just `depth:`)
inherits the other from the project default, it does not reset it.
`depth` here reuses the same N-hop-neighborhood meaning as the full
widget's `depth`, but `root` is always the current page — there's no
mini-panel shortcode call to attach a `root=` kwarg to.

**Exclude** (`quarto-graph: exclude:` in `_quarto.yml`, project-level only):
a list of quarto-graph's own patterns (trailing `/` = a directory and
everything under it, otherwise a plain glob) naming pages that don't
participate in the wikilink graph at all, a **full opt-out**, not a
display filter on the graph widget. An excluded page is never scanned,
can't be linked *to*. A `[[wikilink]]` pointing at it comes back
unresolved, the same as a typo. Independent of whether Quarto itself
renders the page. No page-level frontmatter override yet (unlike Sidebar
config's cascade); if one's added later, follow that same project-default →
page-override pattern.
_Avoid_ conflating with Quarto's own `project: render:` list, which
controls what Quarto renders and is read automatically via `quarto
inspect` (see `docs/adr/0004-delegate-file-discovery-to-quarto-inspect.md`);
`exclude:` is a narrower, additional cut on top of that, scoped only to the
wikilink graph.
