"""Pure resolution logic: page parsing, wikilink/alias resolution.

No file writing here, no output-path computation — a resolved wikilink is a
root-relative link to the target page's own source path, and Quarto's own
project link rewriting turns that into the real final URL. Extracted so the
pre-render pass, the Lua filter's Python-side counterpart data, and any
future editor tooling share exactly one implementation of "what does this
wikilink resolve to."
"""

import re
from pathlib import Path, PurePosixPath

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)(?:#([^\]\[|]+))?(?:\|([^\]\[]+))?\]\]")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

# Side-channel files shared between prerender.py (writer), the Lua filter
# (reader of REGISTRY_PATH, writer of one file per page under PAGES_DIR),
# and postrender.py (reader of both) -- see
# docs/adr/0001-non-destructive-render-time-resolution.md.
REGISTRY_PATH = Path(".quarto") / "quarto-graph" / "registry.json"
PAGES_DIR = Path(".quarto") / "quarto-graph" / "pages"


def normalize_ws(s):
    return re.sub(r"\s+", " ", s.strip())


def anchor_slug(heading):
    return re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", heading.strip().lower()))


def _walk_fences(text):
    """Split text into ("region", start_line, joined_text) blocks for each
    maximal run of non-fenced lines, and ("line", index, line) for every
    fence-delimiter or fenced-content line, in original order. Lines are
    0-indexed. Shared by anything that needs to skip fenced code blocks when
    scanning for wikilinks."""
    lines = text.split("\n")
    in_fence = False
    region_start = 0
    region_lines = []

    def flush():
        if region_lines:
            yield ("region", region_start, "\n".join(region_lines))
            region_lines.clear()

    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            yield from flush()
            in_fence = not in_fence
            yield ("line", i, line)
        elif in_fence:
            yield from flush()
            yield ("line", i, line)
        else:
            if not region_lines:
                region_start = i
            region_lines.append(line)
    yield from flush()


def find_wikilinks_outside_fences(text):
    """Locate every WIKILINK_RE match outside fenced code blocks, returning
    (line, col, match) triples with 1-indexed positions.

    Used both to build the backlink map (pre-render) and for `quarto-graph
    check`'s live editor diagnostics, which needs a position per unresolved
    link."""
    hits = []
    for kind, start_line, region_text in _walk_fences(text):
        if kind != "region":
            continue
        for m in WIKILINK_RE.finditer(region_text):
            line_offset = region_text.count("\n", 0, m.start())
            line_start = region_text.rfind("\n", 0, m.start()) + 1
            col = m.start() - line_start
            hits.append((start_line + line_offset + 1, col + 1, m))
    return hits


def discover_paths(project_root):
    """Every .qmd/.md page under project_root, skipping any path with a
    component starting with "." or "_" -- the same leading-underscore
    exclusion Quarto's own project file discovery applies (a real Quarto
    convention, confirmed the hard way once -- see
    docs/adr/0001-non-destructive-render-time-resolution.md).

    Used as a fallback page-discovery mechanism: normally the pre-render
    pass gets the project's exact file list handed to it by Quarto via
    QUARTO_PROJECT_INPUT_FILES, but that list comes back empty on a
    `quarto preview` session's own initial pre-render pass (confirmed
    empirically) -- and it's always empty for `quarto-graph check`,
    standalone editor tooling with no live Quarto render to read it from.
    """
    project_root = Path(project_root)
    return sorted(
        {
            p for pattern in ("*.qmd", "*.md")
            for p in project_root.rglob(pattern)
            if not any(part.startswith((".", "_")) for part in p.relative_to(project_root).parts)
        }
    )


def parse_page(path, project_root):
    raw = path.read_text(encoding="utf-8")
    meta = {}
    m = FRONTMATTER_RE.match(raw)
    body = raw[m.end():] if m else raw
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            print("WARNING: bad frontmatter in {}: {}".format(path, exc))
    meta = meta if isinstance(meta, dict) else {}
    rel = PurePosixPath(path.relative_to(project_root).as_posix())
    return {
        "src": path,
        "rel": rel,
        "body": body,
        "meta": meta,
        "title": meta.get("title") or path.stem,
        "type": str(meta.get("type") or "").lower(),
    }


def build_registry(pages):
    """Map every name a wikilink can target (case-insensitive) -> page: each
    page's own `title:` (its most reliable human-typed name — a real
    Quarto project commonly names every source file `index.qmd`, inside a
    slug-named folder, so the filename stem alone isn't a usable default),
    its raw filename stem (still useful for a flat, one-file-per-page
    project), and every name in its `also-known-as:` frontmatter list.
    Deliberately not Quarto's own `aliases:` key — that key's values are
    URLs Quarto turns into redirect stubs, a different concept from a
    free-text alternate name for wikilink matching."""
    registry = {}

    def register(name, page):
        key = str(name).strip().lower()
        if not key:
            return
        existing = registry.get(key)
        if existing is not None and existing is not page:
            print("WARNING: duplicate link target '{}' ({} vs {}); keeping {}".format(
                name, existing["rel"], page["rel"], existing["rel"]))
            return
        registry[key] = page

    for page in pages:
        register(page["title"], page)
    for page in pages:
        # "index" is not a usable default name -- a real Quarto project
        # commonly names every page's source file index.qmd (inside a
        # slug-named folder), so every such page would collide on it.
        if page["src"].stem.lower() != "index":
            register(page["src"].stem, page)
    for page in pages:
        also_known_as = page["meta"].get("also-known-as") or []
        if isinstance(also_known_as, str):
            also_known_as = [also_known_as]
        for name in also_known_as:
            register(name, page)
    return registry


def build_backlinks(pages, registry):
    """Scan every page's wikilinks and resolve them against the registry.

    Only the wikilink's target matters for the backlink map itself (not
    anchor/display) — constructing a per-occurrence href is the Lua
    filter's job at each page's own render time, not this pre-render pass.

    Returns (backlinks, unresolved):
    - backlinks: {target_page: [source_page, ...]}, one entry per distinct
      linking page (a page linking to the same target twice backlinks once).
    - unresolved: [{"page", "line", "col", "target", "text"}, ...], in scan
      order — line/col are for `quarto-graph check`'s editor diagnostics;
      the pre-render pass only needs "page"/"text" for its warning.
    """
    backlinks = {}
    unresolved = []
    for page in pages:
        seen_targets = set()
        for line, col, match in find_wikilinks_outside_fences(page["body"]):
            target = match.group(1)
            hit = registry.get(normalize_ws(target).lower())
            if hit is None:
                unresolved.append({
                    "page": page, "line": line, "col": col,
                    "target": target, "text": match.group(0),
                })
                continue
            if hit is page or hit["rel"] in seen_targets:
                continue
            seen_targets.add(hit["rel"])
            backlinks.setdefault(hit["rel"], []).append(page)
    return backlinks, unresolved
