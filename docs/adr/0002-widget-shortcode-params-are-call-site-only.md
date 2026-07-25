# Widget shortcode params (width/height/depth/root/expandable) are call-site-only, no _quarto.yml cascade

The sidebar mini-panel just established a project-default-plus-page-override
cascade pattern (`quarto-graph: sidebar:` in `_quarto.yml`, overridable per
page). The full-graph widget's new params could have followed the same
pattern, but don't: `root` and `depth` are inherently per-instance (a
project-wide "default root page" doesn't generalize the way a boolean
on/off does — a project can have any number of `{{< quarto-graph-full >}}`
calls, each reasonably centered on a different page), and a project-wide
default for `width`/`height`/`expandable` wasn't asked for. Decided to keep
these as shortcode kwargs only, matching the user's own framing
("parameterize on the shortcode call"), rather than extending the cascade
pattern to params where it doesn't obviously fit.
