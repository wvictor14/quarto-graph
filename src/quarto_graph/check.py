"""Live-diagnostics scan: report unresolved wikilinks without writing any
output files.

Standalone page discovery (core.discover_paths) since editor tooling runs
outside a live Quarto render and has no QUARTO_PROJECT_INPUT_FILES to read
(that's only handed to prerender.py by Quarto itself, mid-render).
discover_paths shells out to `quarto inspect` whenever project_root has a
_quarto.yml/_quarto.yaml, so the `quarto` CLI must be on PATH for a real
project; only a bare folder of notes with no project file skips it.
"""

from pathlib import Path

from .core import build_backlinks, build_registry, discover_paths, parse_page


def discover_pages(project_root):
    project_root = Path(project_root)
    return [parse_page(p, project_root) for p in discover_paths(project_root)]


def check_links(project_root):
    """Scan every page under project_root for unresolved [[wikilinks]].

    Returns a list of dicts: {"file", "line", "col", "target", "text"},
    one per unresolved link, in scan order.
    """
    pages = discover_pages(project_root)
    registry = build_registry(pages)
    _backlinks, unresolved = build_backlinks(pages, registry)
    return [
        {
            "file": str(item["page"]["rel"]),
            "line": item["line"],
            "col": item["col"],
            "target": item["target"],
            "text": item["text"],
        }
        for item in unresolved
    ]
