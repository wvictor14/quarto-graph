"""Pure resolution logic: page parsing, wikilink/alias resolution.

No file writing here, no output-path computation — a resolved wikilink is a
root-relative link to the target page's own source path, and Quarto's own
project link rewriting turns that into the real final URL. Extracted so the
pre-render pass, the Lua filter's Python-side counterpart data, and any
future editor tooling share exactly one implementation of "what does this
wikilink resolve to."
"""

import re
import sys
from pathlib import Path, PurePosixPath

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\[|#]+)(?:#([^\]\[|]+))?(?:\|([^\]\[]+))?\]\]")
MARKDOWN_LINK_RE = re.compile(
    r"(?<!!)\[([^\]]*)\]\("
    r"(?:<([^<>\n]*)>|([^()\s][^()]*?))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)
URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")

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


def _find_pattern_outside_fences(text, pattern):
    """Locate every `pattern` match outside fenced code blocks, returning
    (line, col, match) triples with 1-indexed positions. Shared by wikilink
    and Markdown-link scanning, which both need to skip fenced code blocks
    and inline code spans identically."""
    hits = []
    for kind, start_line, region_text in _walk_fences(text):
        if kind != "region":
            continue
        code_spans = [m.span() for m in INLINE_CODE_SPAN_RE.finditer(region_text)]
        for m in pattern.finditer(region_text):
            if any(start <= m.start() and m.end() <= end for start, end in code_spans):
                continue
            line_offset = region_text.count("\n", 0, m.start())
            line_start = region_text.rfind("\n", 0, m.start()) + 1
            col = m.start() - line_start
            hits.append((start_line + line_offset + 1, col + 1, m))
    return hits


def find_wikilinks_outside_fences(text):
    """Locate every WIKILINK_RE match outside fenced code blocks, returning
    (line, col, match) triples with 1-indexed positions.

    Used both to build the backlink map (pre-render) and for `quarto-graph
    check`'s live editor diagnostics, which needs a position per unresolved
    link."""
    return _find_pattern_outside_fences(text, WIKILINK_RE)


def find_markdown_links_outside_fences(text):
    """Locate every MARKDOWN_LINK_RE match (plain `[text](href)`, not image
    syntax) outside fenced code blocks, returning (line, col, match) triples
    with 1-indexed positions -- same contract as find_wikilinks_outside_fences,
    used by build_backlinks to also treat internal Markdown links as edges."""
    return _find_pattern_outside_fences(text, MARKDOWN_LINK_RE)


def resolve_markdown_href(source_rel, href):
    """Resolve a Markdown link href against the linking page's own rel path
    to a project-root-relative PurePosixPath, or None if it isn't a plain
    internal path -- an external URL (any '<scheme>:'), a protocol-relative
    href ('//host/...'), or a fragment/query-only href. `.`/`..` segments are
    collapsed; a leading '/' is root-relative to the project, otherwise
    relative to source_rel's own directory."""
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href or href.startswith("//") or URL_SCHEME_RE.match(href):
        return None
    if href.startswith("/"):
        segments = href.split("/")
    else:
        segments = list(source_rel.parent.parts) + href.split("/")
    stack = []
    for seg in segments:
        if seg in ("", "."):
            continue
        if seg == "..":
            if stack:
                stack.pop()
            continue
        stack.append(seg)
    return PurePosixPath(*stack) if stack else None


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
            print("WARNING: bad frontmatter in {}: {}".format(path, exc), file=sys.stderr)
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


DEFAULT_SIDEBAR_DEPTH = 1
DEFAULT_SIDEBAR_CONFIG = {"enabled": True, "depth": DEFAULT_SIDEBAR_DEPTH}


def _coerce_depth(value, fallback):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _coerce_sidebar_config(value):
    """Normalizes a raw `sidebar:` value -- the bare bool shorthand or an
    `{enabled, depth}` mapping -- to a plain {"enabled": bool, "depth": int}
    dict. depth floors at 1 (see CONTEXT.md's Depth entry); anything
    unparseable falls back to DEFAULT_SIDEBAR_DEPTH."""
    if isinstance(value, dict):
        return {
            "enabled": bool(value.get("enabled", True)),
            "depth": _coerce_depth(value.get("depth", DEFAULT_SIDEBAR_DEPTH), DEFAULT_SIDEBAR_DEPTH),
        }
    return {"enabled": bool(value), "depth": DEFAULT_SIDEBAR_DEPTH}


def read_project_config(project_root):
    """Load the project-wide `quarto-graph:` mapping from `_quarto.yml` (or
    `_quarto.yaml`) at project_root, returning {"sidebar": {"enabled": bool,
    "depth": int}} -- the global default for the sidebar mini-panel.
    Missing file, bad YAML, or a missing `sidebar:` key all fall back to
    DEFAULT_SIDEBAR_CONFIG (bad YAML also warns to stderr, same as
    parse_page's own frontmatter handling)."""
    project_root = Path(project_root)
    config_path = project_root / "_quarto.yml"
    if not config_path.exists():
        config_path = project_root / "_quarto.yaml"
    if not config_path.exists():
        return {"sidebar": dict(DEFAULT_SIDEBAR_CONFIG)}
    try:
        doc = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print("WARNING: bad YAML in {}: {}".format(config_path, exc), file=sys.stderr)
        return {"sidebar": dict(DEFAULT_SIDEBAR_CONFIG)}
    quarto_graph = doc.get("quarto-graph") if isinstance(doc, dict) else None
    quarto_graph = quarto_graph if isinstance(quarto_graph, dict) else {}
    if "sidebar" not in quarto_graph:
        return {"sidebar": dict(DEFAULT_SIDEBAR_CONFIG)}
    return {"sidebar": _coerce_sidebar_config(quarto_graph["sidebar"])}


def page_sidebar_config(page, project_config):
    """Resolved {"enabled": bool, "depth": int} sidebar config for this
    page. Each field resolves independently: the page's own `quarto-graph:
    sidebar:` frontmatter overrides only the fields it actually sets (a
    page setting just `depth:` keeps the project's `enabled`, and vice
    versa) -- see CONTEXT.md's Sidebar config entry."""
    project_sidebar = project_config["sidebar"]
    page_config = page["meta"].get("quarto-graph")
    if not (isinstance(page_config, dict) and "sidebar" in page_config):
        return project_sidebar
    raw = page_config["sidebar"]
    if not isinstance(raw, dict):
        return {"enabled": bool(raw), "depth": project_sidebar["depth"]}
    return {
        "enabled": bool(raw["enabled"]) if "enabled" in raw else project_sidebar["enabled"],
        "depth": _coerce_depth(raw["depth"], project_sidebar["depth"]) if "depth" in raw else project_sidebar["depth"],
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
                name, existing["rel"], page["rel"], existing["rel"]), file=sys.stderr)
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
    """Scan every page's wikilinks and internal Markdown links, and resolve
    each against the registry (wikilinks) or the other pages' own rel paths
    (Markdown links).

    Only the link's target matters for the backlink map itself (not
    anchor/display) — constructing a per-occurrence href is the Lua
    filter's job at each page's own render time, not this pre-render pass.
    A Markdown link that doesn't resolve to another project page (an
    external URL, an asset, a typo'd path, ...) is left alone entirely,
    since unlike an unresolved wikilink it's not necessarily a mistake, so
    it never lands in `unresolved`.

    Returns (backlinks, unresolved):
    - backlinks: {target_page: [source_page, ...]}, one entry per distinct
      linking page (a page linking to the same target twice, even via a mix
      of wikilink and Markdown link, backlinks once).
    - unresolved: [{"page", "line", "col", "target", "text"}, ...], in scan
      order — line/col are for `quarto-graph check`'s editor diagnostics;
      the pre-render pass only needs "page"/"text" for its warning.
    """
    path_index = {str(page["rel"]): page for page in pages}
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
        for line, col, match in find_markdown_links_outside_fences(page["body"]):
            href = match.group(2) if match.group(2) is not None else match.group(3)
            target_rel = resolve_markdown_href(page["rel"], href.rstrip())
            if target_rel is None:
                continue
            hit = path_index.get(str(target_rel))
            if hit is None or hit is page or hit["rel"] in seen_targets:
                continue
            seen_targets.add(hit["rel"])
            backlinks.setdefault(hit["rel"], []).append(page)
    return backlinks, unresolved
