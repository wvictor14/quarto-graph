-- Ships graph.js/graph.css as a proper Quarto HTML dependency.
--
-- add_html_dependency is how Quarto works out the correct relative path
-- for every page, no matter how deep it is in the folder tree.
function Meta(meta)
  quarto.doc.add_html_dependency({
    name = "quarto-graph",
    version = "0.1.0",
    scripts = { "graph.js" },
    stylesheets = { "graph.css" },
  })
  return meta
end

-- Wikilink resolution + backlinks, both driven by a registry
-- quarto_graph.prerender builds once across every page Quarto is about to
-- render. Resolution here only transforms the in-memory Pandoc AST for this
-- one render; the .qmd source is never rewritten

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

-- quarto.doc.input_file/output_file are absolute paths; strip the project
-- root prefix so both sides of the Python/Lua boundary key pages by the
-- same project-relative identity quarto_graph.core.parse_page uses.
local function project_rel(path, base)
  return path:sub(#base + 2)
end

-- Mirrors quarto_graph.core.anchor_slug. This duplicates that logic on
-- the Lua side of the Python/Lua boundary, since there's no way to share
-- code between the two.
local function anchor_slug(heading)
  local slug = heading:lower():gsub("[^%w%s%-]", "")
  return slug:gsub("%s+", "-")
end

-- "Target", "Target|display", "Target#Heading", "Target#Heading|display".
local function parse_wikilink(content)
  local target, anchor, display
  local before_pipe, after_pipe = content:match("^(.-)|(.*)$")
  if before_pipe == nil then
    before_pipe = content
  else
    display = after_pipe
  end
  local before_hash, after_hash = before_pipe:match("^(.-)#(.*)$")
  if before_hash == nil then
    target = before_pipe
  else
    target = before_hash
    anchor = after_hash
  end
  return target, anchor, display
end

local function resolve_wikilink(content, reg)
  local target, anchor, display = parse_wikilink(content)
  local key = target:lower():gsub("%s+", " "):match("^%s*(.-)%s*$")
  local hit_rel = reg.registry[key]
  if hit_rel == nil then
    return nil
  end
  local page = reg.pages[hit_rel]
  local text = display or (page and page.title) or target
  local href = "/" .. hit_rel
  if anchor ~= nil then
    href = href .. "#" .. anchor_slug(anchor)
  end
  return pandoc.Link(text, href)
end

-- Splits a chunk of plain text on whitespace into Str/Space inlines,
-- collapsing whitespace runs into a single Space the same way Markdown
-- itself does.
local function text_to_inlines(text)
  local out = pandoc.List({})
  local i, n = 1, #text
  while i <= n do
    local s, e = text:find("%s+", i)
    if s == i then
      out:insert(pandoc.Space())
      i = e + 1
    else
      local word_end = (s or (n + 1)) - 1
      out:insert(pandoc.Str(text:sub(i, word_end)))
      i = word_end + 1
    end
  end
  return out
end

-- Finds every [[wikilink]] in a buffered literal-text run and rebuilds it
-- as plain inlines interleaved with resolved pandoc.Link nodes. Unresolved
-- targets are left as literal text, brackets and all, matching the
-- pre-render pass's own "not found -> left as plain text" contract.
local function resolve_run(text, reg)
  local out = pandoc.List({})
  local pos = 1
  while true do
    local s, e, content = text:find("%[%[(.-)%]%]", pos)
    if s == nil then
      out:extend(text_to_inlines(text:sub(pos)))
      break
    end
    if s > pos then
      out:extend(text_to_inlines(text:sub(pos, s - 1)))
    end
    local link = resolve_wikilink(content, reg)
    if link ~= nil then
      out:insert(link)
    else
      quarto.log.warning("unresolved wikilink [[" .. content .. "]]")
      out:extend(text_to_inlines("[[" .. content .. "]]"))
    end
    pos = e + 1
  end
  return out
end

-- A single Str can't hold a multi-word wikilink target. "[[Getting
-- Started]]" tokenizes as Str("[[Getting"), Space, Str("Started]]"), not
-- one Str. So this buffers consecutive Str/Space/SoftBreak inlines into
-- one literal-text run and only rebuilds that run, leaving any other
-- inline (Emph, Strong, Code, an existing Link, ...) untouched. Pandoc
-- recurses into those on its own.
function Inlines(inlines)
  local reg = load_registry()
  if not reg then
    return nil
  end
  local out = pandoc.List({})
  local buffer = {}
  local function flush()
    if #buffer > 0 then
      out:extend(resolve_run(table.concat(buffer), reg))
      buffer = {}
    end
  end
  for _, inline in ipairs(inlines) do
    if inline.t == "Str" then
      table.insert(buffer, inline.text)
    elseif inline.t == "Space" or inline.t == "SoftBreak" then
      table.insert(buffer, " ")
    else
      flush()
      out:insert(inline)
    end
  end
  flush()
  return out
end

-- Appends this page's own "## Backlinks" section, if any, and records
-- this page's own real output URL so postrender.py can assemble
-- graph.json from it, instead of guessing at a naming convention.
function Pandoc(doc)
  local reg = load_registry()
  local project_dir = quarto.project.directory
  if reg == nil or reg == false or project_dir == nil then
    return doc
  end

  local rel = project_rel(quarto.doc.input_file, project_dir)
  local page = reg.pages[rel]
  local sidebar = page and page.sidebar
  if sidebar ~= nil then
    if sidebar.enabled == false then
      quarto.doc.include_text("in-header", '<meta name="quarto-graph-sidebar" content="false">')
    elseif sidebar.depth ~= nil and sidebar.depth ~= 1 then
      quarto.doc.include_text(
        "in-header",
        '<meta name="quarto-graph-sidebar-depth" content="' .. tostring(sidebar.depth) .. '">'
      )
    end
  end

  local backlinks = reg.backlinks[rel]
  if backlinks ~= nil and #backlinks > 0 then
    local items = pandoc.List({})
    for _, b in ipairs(backlinks) do
      items:insert(pandoc.Plain({ pandoc.Link(b.title, "/" .. b.rel) }))
    end
    doc.blocks:insert(pandoc.Header(2, "Backlinks"))
    doc.blocks:insert(pandoc.BulletList(items))
  end

  local output_dir = quarto.project.output_directory
  local output_file = quarto.doc.output_file
  local output_url = output_file
  if output_dir ~= nil then
    output_url = project_rel(output_file, output_dir)
  end
  -- A directory-index page (foo/index.html, or the site root's own
  -- index.html) is actually *served* at foo/ or the site root, with no
  -- "index.html" in the address bar. graph.js's own "which node is this
  -- page" matching compares against that served form, not the physical
  -- file path. This is just how any static file server handles directory
  -- indexes, not a guess at Quarto's own naming convention.
  if output_url == "index.html" then
    output_url = ""
  elseif output_url:match("/index%.html$") then
    output_url = output_url:sub(1, -("index.html"):len() - 1)
  end
  local safe_name = rel:gsub("[/\\.]", "_")
  local record_file = io.open(project_dir .. "/.quarto/quarto-graph/pages/" .. safe_name .. ".json", "w")
  if record_file ~= nil then
    record_file:write(quarto.json.encode({ rel = rel, output_url = output_url }))
    record_file:close()
  end

  return doc
end
