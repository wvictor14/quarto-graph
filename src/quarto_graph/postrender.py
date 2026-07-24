"""Post-render pass: assemble graph.json from the pre-render registry and
each page's own real rendered output path.

Node URLs come from PAGES_DIR -- one small file per page, written by the
Lua filter during that page's own render from Quarto's own
quarto.doc.output_file -- never predicted from a naming convention (see
docs/adr/0001-non-destructive-render-time-resolution.md).
"""

import json
from pathlib import Path

from .core import PAGES_DIR, REGISTRY_PATH


def run_postrender(project_root, output_dir):
    project_root = Path(project_root)
    registry = json.loads((project_root / REGISTRY_PATH).read_text(encoding="utf-8"))

    pages_dir = project_root / PAGES_DIR
    output_urls = {}
    page_files = sorted(pages_dir.glob("*.json")) if pages_dir.is_dir() else []
    for f in page_files:
        record = json.loads(f.read_text(encoding="utf-8"))
        output_urls[record["rel"]] = record["output_url"]

    rels = sorted(registry["pages"])
    index = {rel: i for i, rel in enumerate(rels)}
    nodes = [
        {
            "title": registry["pages"][rel]["title"],
            "type": registry["pages"][rel]["type"],
            "url": output_urls.get(rel, ""),
        }
        for rel in rels
    ]
    edges = sorted(set(
        (min(index[target], index[src["rel"]]), max(index[target], index[src["rel"]]))
        for target, sources in registry["backlinks"].items()
        for src in sources
        if target in index and src["rel"] in index
    ))
    payload = {"nodes": nodes, "edges": [list(e) for e in edges]}

    output_dir = Path(output_dir)
    (output_dir / "graph.json").write_text(json.dumps(payload), encoding="utf-8")

    for f in page_files:
        f.unlink()

    return payload
