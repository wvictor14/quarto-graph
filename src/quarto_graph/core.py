"""Page parsing and wikilink/alias resolution.

Doesn't write files or work out output paths. A resolved wikilink is just a
root-relative link to the target page's source path. Quarto rewrites that
into the real URL when it renders. Kept in one place so the pre-render
pass, the Lua filter's Python-side data, and any future editor tooling all
agree on what a wikilink resolves to.
"""

import fnmatch
import json
import re
import subprocess
import sys
import time
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
# (reads REGISTRY_PATH, writes one file per page under PAGES_DIR), and
# postrender.py (reads both). This keeps the source .qmd files untouched.
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
    with 1-indexed positions. Same contract as find_wikilinks_outside_fences.
    Used by build_backlinks to also treat internal Markdown links as edges."""
    return _find_pattern_outside_fences(text, MARKDOWN_LINK_RE)


def resolve_markdown_href(source_rel, href):
    """Resolve a Markdown link href against the linking page's own rel path
    to a project-root-relative PurePosixPath. Returns None if it isn't a
    plain internal path: an external URL (any '<scheme>:'), a
    protocol-relative href ('//host/...'), or a fragment/query-only href.
    `.`/`..` segments are collapsed; a leading '/' is root-relative to the
    project, otherwise relative to source_rel's own directory."""
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


# Filenames Quarto never renders by default, regardless of dot/underscore
# prefixing (confirmed against Quarto 1.9.37). Applied by hand in the
# no-project fallback branch of discover_paths, since there's no `quarto
# inspect` to do it for us there.
DEFAULT_EXCLUDE_FILENAMES = {"README.md", "README.qmd", "CLAUDE.md", "AGENTS.md"}


def _quarto_project_config_path(project_root):
    """The project's `_quarto.yml`/`_quarto.yaml` path, or None if neither
    exists. Even a bare file with no `project:` key, just a `quarto-graph:`
    block, is enough for Quarto to treat project_root as a real project
    (confirmed by testing). This same existence check picks
    discover_paths's discovery mechanism and gates read_project_config."""
    project_root = Path(project_root)
    yml = project_root / "_quarto.yml"
    if yml.exists():
        return yml
    yaml_path = project_root / "_quarto.yaml"
    return yaml_path if yaml_path.exists() else None


def _is_excluded(rel, patterns):
    """True if `rel` matches any `quarto-graph: exclude:` pattern. A
    trailing "/" excludes that directory and everything under it;
    anything else is matched with fnmatch against the posix path string.
    Uses fnmatchcase, not fnmatch, so case sensitivity doesn't depend on
    the host OS. This is quarto-graph's own small exclude-only syntax, not
    a copy of Quarto's `render:` glob spec, so there's no negation."""
    rel_str = str(rel)
    for pattern in patterns:
        if pattern.endswith("/"):
            if rel.is_relative_to(PurePosixPath(pattern.rstrip("/"))):
                return True
        elif fnmatch.fnmatchcase(rel_str, pattern):
            return True
    return False


def discover_paths(project_root, project_config=None):
    """Every page quarto-graph treats as part of the project, minus this
    project's own `quarto-graph: exclude:` patterns. Excluding a page is a
    full opt-out: it's never scanned, and a [[wikilink]] pointing at it
    comes back unresolved, same as a typo.

    `project_config` lets a caller that already loaded
    `read_project_config` (prerender.py, which also needs it for sidebar
    config) pass it in directly, instead of parsing `_quarto.yml` again.
    Callers that only need the exclude list (check.py) can skip it and let
    this function load it.

    There are two ways to find pages, depending on whether project_root
    has a `_quarto.yml`/`_quarto.yaml`:

    - Real project: ask `quarto inspect` for `files.input`, Quarto's own
      fully-resolved render list. This respects a custom `project:
      render:` glob/negation list and Quarto's default exclusions
      (dot/underscore paths, README, CLAUDE.md, AGENTS.md) exactly,
      instead of reimplementing Quarto's glob rules and risking a
      mismatch. Only `.qmd`/`.md` entries are kept; `quarto inspect` can
      also list `.ipynb`/`.Rmd` files, which this project's Markdown-only
      parsing can't handle.
    - No project file: `quarto inspect` refuses to run, so this falls back
      to a plain recursive scan with the same default exclusions applied
      by hand. This is the path `quarto-graph check` uses for a bare
      folder of notes that was never wrapped in a Quarto project.
    """
    project_root = Path(project_root)
    config_path = _quarto_project_config_path(project_root)
    if config_path is not None:
        resolved_root = project_root.resolve()
        # `quarto preview` can fire more than one render for the same page in
        # quick succession (e.g. a double GET), each spawning its own `quarto
        # inspect` here concurrently. They race on Quarto's shared `.quarto`
        # cache dir and one occasionally exits with an error. Retry once
        # before giving up, since the next call normally succeeds.
        exc = None
        for attempt in range(2):
            try:
                result = subprocess.run(
                    ["quarto", "inspect", str(resolved_root)],
                    capture_output=True, text=True, check=True,
                )
                exc = None
                break
            except subprocess.CalledProcessError as e:
                exc = e
                if attempt == 0:
                    time.sleep(0.5)
            except FileNotFoundError as e:
                exc = e
                break
        if exc is not None:
            stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
            raise RuntimeError(
                "quarto-graph needs the `quarto` CLI to inspect {} (it has a "
                "_quarto.yml/_quarto.yaml). Install Quarto, or run against a "
                "plain folder with no project file.{}".format(
                    project_root, "\n" + stderr if stderr else ""
                )
            ) from exc
        paths = {
            project_root / Path(f).relative_to(resolved_root)
            for f in json.loads(result.stdout)["files"]["input"]
            if f.endswith((".qmd", ".md"))
        }
    else:
        paths = {
            p for pattern in ("*.qmd", "*.md")
            for p in project_root.rglob(pattern)
            if not any(part.startswith((".", "_")) for part in p.relative_to(project_root).parts)
            and p.name not in DEFAULT_EXCLUDE_FILENAMES
        }

    if project_config is None:
        project_config = read_project_config(project_root, config_path=config_path)
    exclude_patterns = project_config["exclude"]
    return sorted(
        p for p in paths
        if not _is_excluded(PurePosixPath(p.relative_to(project_root).as_posix()), exclude_patterns)
    )


def identifier_chain(rel):
    """The path segments identifying a page for wikilink-registry purposes.
    Folds a trailing `index` stem into its containing folder, since an
    `index.qmd` *is* its folder, the same way Obsidian folder-notes and
    Quartz treat it, rather than a separately-named page called "index".

    `a/b/c/index.qmd` -> ("a", "b", "c")
    `notes/Overview.qmd` -> ("notes", "Overview")
    top-level `index.qmd` -> ("index",). Nothing to fold into, and there's
    only ever one project-root page, so no collision risk.
    """
    parts = rel.parent.parts
    if rel.stem.lower() == "index" and parts:
        return parts
    return parts + (rel.stem,)


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
    chain = identifier_chain(rel)
    return {
        "src": path,
        "rel": rel,
        "body": body,
        "meta": meta,
        "title": meta.get("title") or chain[-1],
        "type": str(meta.get("type") or "").lower(),
    }


DEFAULT_SIDEBAR_DEPTH = 1
DEFAULT_SIDEBAR_CONFIG = {"enabled": True, "depth": DEFAULT_SIDEBAR_DEPTH}


def _coerce_depth(value, fallback):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        print("WARNING: bad depth value {!r}, falling back to {}".format(value, fallback), file=sys.stderr)
        return fallback


def _coerce_sidebar_config(value):
    """Normalizes a raw `sidebar:` value, the bare bool shorthand or an
    `{enabled, depth}` mapping, to a plain {"enabled": bool, "depth": int}
    dict. depth floors at 1 (see CONTEXT.md's Depth entry). Anything
    unparseable falls back to DEFAULT_SIDEBAR_DEPTH."""
    if isinstance(value, dict):
        return {
            "enabled": bool(value.get("enabled", True)),
            "depth": _coerce_depth(value.get("depth", DEFAULT_SIDEBAR_DEPTH), DEFAULT_SIDEBAR_DEPTH),
        }
    return {"enabled": bool(value), "depth": DEFAULT_SIDEBAR_DEPTH}


def _coerce_exclude_config(value):
    """Normalizes a raw `quarto-graph: exclude:` value to a list of pattern
    strings for _is_excluded. A non-list value, or a non-string entry
    within it, warns to stderr and is dropped, same tolerant style as bad
    depth/bad YAML elsewhere in this module."""
    if not isinstance(value, list):
        print("WARNING: quarto-graph: exclude: must be a list, got {!r}; ignoring".format(value), file=sys.stderr)
        return []
    patterns = []
    for item in value:
        if isinstance(item, str):
            patterns.append(item)
        else:
            print("WARNING: ignoring non-string exclude pattern {!r}".format(item), file=sys.stderr)
    return patterns


def read_project_config(project_root, config_path=None):
    """Load the project-wide `quarto-graph:` mapping from `_quarto.yml` (or
    `_quarto.yaml`) at project_root, returning {"sidebar": {"enabled": bool,
    "depth": int}, "exclude": [pattern, ...]}. Missing file, bad YAML, or a
    missing key all fall back to that key's default independently (bad YAML
    also warns to stderr, same as parse_page's own frontmatter handling).

    `config_path` lets a caller that already resolved
    `_quarto_project_config_path` (discover_paths) pass it in directly
    instead of this function re-doing that same existence check."""
    project_root = Path(project_root)
    defaults = {"sidebar": dict(DEFAULT_SIDEBAR_CONFIG), "exclude": []}
    if config_path is None:
        config_path = _quarto_project_config_path(project_root)
    if config_path is None:
        return defaults
    try:
        doc = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print("WARNING: bad YAML in {}: {}".format(config_path, exc), file=sys.stderr)
        return defaults
    quarto_graph = doc.get("quarto-graph") if isinstance(doc, dict) else None
    quarto_graph = quarto_graph if isinstance(quarto_graph, dict) else {}
    return {
        "sidebar": _coerce_sidebar_config(quarto_graph.get("sidebar", DEFAULT_SIDEBAR_CONFIG)),
        "exclude": _coerce_exclude_config(quarto_graph.get("exclude", [])),
    }


def page_sidebar_config(page, project_config):
    """Resolved {"enabled": bool, "depth": int} sidebar config for this
    page. Each field resolves independently: the page's own `quarto-graph:
    sidebar:` frontmatter overrides only the fields it actually sets (a
    page setting just `depth:` keeps the project's `enabled`, and vice
    versa). See CONTEXT.md's Sidebar config entry."""
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
    """Map every name a wikilink can target (case-insensitive) to a page.
    Each page registers: its own `title:` (the most reliable human-typed
    name, since a real Quarto project commonly names every source file
    `index.qmd` inside a slug-named folder, so the filename stem alone
    isn't a usable default), its folder-path identifier (see
    `identifier_chain`: the raw filename stem for a one-file-per-page
    project, or the containing folder's name for an `index.qmd`
    folder-note), and every name in its `also-known-as:` frontmatter list.
    This is deliberately not Quarto's own `aliases:` key, since that key's
    values are URLs Quarto turns into redirect stubs, a different concept
    from a free-text alternate name for wikilink matching.

    Both the folder-path identifier and an explicit `title:` also register
    progressively longer ancestor-qualified forms (`[[api]]` ->
    `[[docs/api]]` -> `[[project/docs/api]]`). So when a name collides
    between two pages, most commonly every folder's title-less `index.qmd`
    colliding on its own folder name, it stays individually reachable by
    qualifying it with enough of its path to be unique. Same way Foam
    disambiguates same-named notes in different folders.

    Bare `"index"` itself is never a usable target, since every folder's
    index.qmd would otherwise "collide" on it, and that isn't a real
    ambiguity. `identifier_chain` folds it into its folder for every page
    except the project's own top-level `index.qmd`, the one page where
    "index" is unique by construction.
    """
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
        chain = identifier_chain(page["rel"])
        # k=1 (the bare folder/stem name) is already registered above via
        # `page["title"]` whenever there's no explicit `title:` frontmatter
        # (title falls back to exactly this). Only register it again here
        # when a custom title differs from it, so a folder note is still
        # reachable by its bare folder name even when it also has its own
        # title. Registering the same (page, key) pair twice is harmless,
        # but re-registering it for every page would double every
        # duplicate-target warning.
        start = 1 if page["meta"].get("title") else 2
        for k in range(start, len(chain) + 1):
            register("/".join(chain[-k:]), page)
    for page in pages:
        title = page["meta"].get("title")
        if not title:
            continue
        ancestors = page["rel"].parent.parts
        for j in range(1, len(ancestors) + 1):
            register("/".join(ancestors[-j:] + (str(title),)), page)
    for page in pages:
        # An index.qmd also keeps resolving by its literal, unfolded
        # "folder/index" spelling, for someone who'd rather write
        # `[[page1/index]]` explicitly than rely on the folder-note-style
        # bare `[[page1]]` above. Starts at 2 ancestors (`folder/index`),
        # never bare `index` alone, for the same reason as `identifier_chain`.
        if page["rel"].stem.lower() != "index":
            continue
        unfolded = page["rel"].parent.parts + ("index",)
        for k in range(2, len(unfolded) + 1):
            register("/".join(unfolded[-k:]), page)
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

    Only the link's target matters for the backlink map itself, not
    anchor/display text. Building a per-occurrence href is the Lua filter's
    job at each page's own render time, not this pre-render pass. A
    Markdown link that doesn't resolve to another project page (an
    external URL, an asset, a typo'd path, ...) is left alone entirely,
    since unlike an unresolved wikilink it's not necessarily a mistake, so
    it never lands in `unresolved`.

    Returns (backlinks, unresolved):
    - backlinks: {target_page: [source_page, ...]}, one entry per distinct
      linking page (a page linking to the same target twice, even via a mix
      of wikilink and Markdown link, backlinks once).
    - unresolved: [{"page", "line", "col", "target", "text"}, ...], in scan
      order. line/col are for `quarto-graph check`'s editor diagnostics;
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
