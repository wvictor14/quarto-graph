-- {{< quarto-graph-full >}} -- Injects a full-project graph widget into the
-- page. Each call gets its own generated id (quarto-graph-full-1, -2, ...)
-- so multiple instances can coexist on one page; graph.js mounts each one
-- found via the shared "quarto-graph-full" class, reading its params off
-- data-* attributes.

local registry = nil

local function load_registry()
  if registry ~= nil then
    return registry
  end
  local project_dir = quarto.project.directory
  if project_dir == nil then
    registry = false
    return registry
  end
  local file = io.open(project_dir .. "/.quarto/quarto-graph/registry.json", "r")
  if file == nil then
    registry = false
    return registry
  end
  local content = file:read("*all")
  file:close()
  registry = quarto.json.decode(content)
  return registry
end

-- Resolves a root= kwarg to its target page's rel path (the identity
-- graph.json's own nodes carry, unlike title, which two pages can share):
-- first as a wikilink-style name (title/alias/filename-stem,
-- case-insensitive, via the same registry [[wikilinks]] use -- see
-- filter.lua's resolve_wikilink), falling back to a literal rel source
-- path. Returns nil if neither matches.
local function resolve_root(name, reg)
  local key = name:lower():gsub("%s+", " "):match("^%s*(.-)%s*$")
  local hit_rel = reg.registry[key] or (reg.pages[name] ~= nil and name or nil)
  return hit_rel
end

local function escape_attr(s)
  return s:gsub("&", "&amp;"):gsub('"', "&quot;"):gsub("<", "&lt;"):gsub(">", "&gt;")
end

local function render_div(attrs)
  local parts = { "<div" }
  for _, kv in ipairs(attrs) do
    table.insert(parts, ' ' .. kv[1] .. '="' .. escape_attr(kv[2]) .. '"')
  end
  table.insert(parts, "></div>")
  return table.concat(parts)
end

local counter = 0

return {
  ["quarto-graph-full"] = function(args, kwargs, meta)
    counter = counter + 1
    local attrs = {
      { "id", "quarto-graph-full-" .. counter },
      { "class", "quarto-graph-full" },
    }

    -- Shortcode kwargs arrive as plain Lua strings (already stringified by
    -- Quarto itself), not Pandoc Inlines -- no pandoc.utils.stringify here.
    -- Copied into a plain table first: direct kwargs["root"] indexing on
    -- Quarto's own kwargs object does not reliably return that key's value
    -- for every key name, but iterating it with pairs() does.
    local kw = {}
    for k, v in pairs(kwargs) do
      kw[k] = v
    end

    if kw["width"] then
      table.insert(attrs, { "data-width", kw["width"] })
    end
    if kw["height"] then
      table.insert(attrs, { "data-height", kw["height"] })
    end
    if kw["expandable"] == "true" then
      table.insert(attrs, { "data-expandable", "true" })
    end

    if kw["depth"] then
      local depth = math.max(1, math.floor(tonumber(kw["depth"]) or 1))
      local root_rel = nil
      if kw["root"] then
        local reg = load_registry()
        root_rel = reg and resolve_root(kw["root"], reg)
        if root_rel == nil then
          quarto.log.warning("quarto-graph-full: unresolved root '" .. kw["root"] .. "'; widget not rendered")
          return pandoc.List({})
        end
      end
      table.insert(attrs, { "data-depth", tostring(depth) })
      if root_rel ~= nil then
        table.insert(attrs, { "data-root", root_rel })
      end
    end

    return pandoc.RawBlock("html", render_div(attrs))
  end,
}
