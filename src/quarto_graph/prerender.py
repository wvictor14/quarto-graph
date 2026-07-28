"""Pre-render pass: build the wikilink/alias registry and backlink map
across every page Quarto is about to render, before any single page's own
render starts -- a per-page Lua filter can't discover the rest of the
project on its own. Writes a side-channel file the Lua filter reads at
each page's own render time; this project never rewrites page source
(see docs/adr/0001-non-destructive-render-time-resolution.md).
"""

import json
import os
import sys
from pathlib import Path

from .core import (
    PAGES_DIR,
    REGISTRY_PATH,
    build_backlinks,
    build_registry,
    discover_paths,
    page_sidebar_config,
    parse_page,
    read_project_config,
)


class QuartoGraphError(Exception):
    """Raised when strict=True and unresolved wikilinks remain."""


def run_prerender(project_root, strict=False):
    """Always scans the whole project (core.discover_paths), ignoring
    whatever subset of it Quarto is about to render in this particular
    invocation. QUARTO_PROJECT_INPUT_FILES (handed to a pre-render script)
    looks tempting for this -- zero glob-reimplementation -- but it means
    "files in *this* render," not "every page in the project": confirmed
    empirically that it's empty on a `quarto preview` session's own
    initial pre-render pass, and that it lists only the one file being
    rendered for a single-file `quarto render`/`quarto preview` -- either
    way, exactly the wrong scope for a registry that has to resolve
    wikilinks against every OTHER page too.

    Writes REGISTRY_PATH under project_root and returns the same payload
    (mainly for tests).
    """
    project_root = Path(project_root)
    project_config = read_project_config(project_root)
    pages = [
        parse_page(p, project_root)
        for p in discover_paths(project_root, project_config=project_config)
    ]
    registry = build_registry(pages)
    backlinks, unresolved = build_backlinks(pages, registry)

    payload = {
        "pages": {
            str(p["rel"]): {
                "title": p["title"],
                "type": p["type"],
                "sidebar": page_sidebar_config(p, project_config),
            }
            for p in pages
        },
        "registry": {name: str(page["rel"]) for name, page in registry.items()},
        "backlinks": {
            str(target_rel): sorted(
                ({"title": src["title"], "rel": str(src["rel"])} for src in sources),
                key=lambda s: s["title"],
            )
            for target_rel, sources in backlinks.items()
        },
    }

    registry_path = project_root / REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    # Pre-created here (pre-render always completes before any page's own
    # render starts) so the Lua filter can just write into it directly,
    # with no directory-creation call of its own.
    (project_root / PAGES_DIR).mkdir(parents=True, exist_ok=True)

    quiet = os.environ.get("QUARTO_PROJECT_SCRIPT_QUIET") == "1"
    if not quiet:
        for item in unresolved:
            print("WARNING: unresolved wikilink {} in {}".format(item["text"], item["page"]["rel"]), file=sys.stderr)
        print("quarto-graph prerender: {} pages, {} link targets, {} unresolved wikilinks".format(
            len(pages), len(registry), len(unresolved)), file=sys.stderr)
    if unresolved and strict:
        raise QuartoGraphError("unresolved wikilinks with --strict")

    return payload
