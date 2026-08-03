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
graph.js's rendering options, a rendering detail, not this config concept)

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
widget's `depth`, but `root` is always the current page, since there's no
mini-panel shortcode call to attach a `root=` kwarg to.

**Color scheme** (`quarto-graph: color:` in `_quarto.yml`):
How to color graph nodes. A scheme has a `by` mode (how to bucket a page:
`folder` for its top-level folder, `(root)` for project-top-level pages;
`depth` for its path depth, root = 0; or `custom` for an exact map) and a
`palette` (`okabe-ito` colorblind-safe, `d3-category10` categorical, or
`viridis` sequential for depth shading; qualitative palettes auto-generate
golden-angle-spread colors past their preset size). `custom` schemes carry
a `custom: {bucket: hex}` map; unmapped buckets fall back to gray. Two
built-ins exist, `by-folder` (folder + okabe-ito, the default) and
`by-depth` (depth + viridis); a user scheme with the same name overrides a
built-in, a new name adds one. `default-scheme:` names the scheme widgets
show without an explicit override. Colors are baked into graph.json per
node at post-render; graph.js holds no palette logic and only looks up
`node.colors[activeScheme]`.
_Avoid_: type (an Obsidian skeleton from an old version, deliberately
removed end-to-end; a future `categories:` frontmatter key could replace
it, still out of scope)

**Per-widget scheme** (shortcode):
`{{< quarto-graph-full color-scheme="name" >}}` kwarg overriding which
color scheme that one widget instance uses, instead of
`color: default-scheme:`. Custom maps stay project-level (scheme defined
in `_quarto.yml`, referenced by name here); a shortcode can't carry its
own inline map. Unknown scheme names fall back to the default scheme's
colors, never a hard error.

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
inspect`
`exclude:` is a narrower, additional cut on top of that, scoped only to the
wikilink graph.
