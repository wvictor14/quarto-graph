-- {{< quarto-graph-full >}} -- mounts the full-project graph view. Not
-- auto-generated as a page: this project never writes files into a
-- consuming project (see docs/adr/0001-non-destructive-render-time-resolution.md),
-- so you place this shortcode yourself, on whatever page you want it on.
return {
  ["quarto-graph-full"] = function(args, kwargs, meta)
    return pandoc.RawBlock("html", '<div id="quarto-graph-full"></div>')
  end,
}
