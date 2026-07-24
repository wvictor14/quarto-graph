-- {{< quarto-graph-full >}} -- Injects the full-project graph widget into page.
return {
  ["quarto-graph-full"] = function(args, kwargs, meta)
    return pandoc.RawBlock("html", '<div id="quarto-graph-full"></div>')
  end,
}
