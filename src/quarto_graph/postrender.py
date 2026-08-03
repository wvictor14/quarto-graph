"""Post-render pass: assemble graph.json from the pre-render registry and
each page's own real rendered output path.

Node URLs come from PAGES_DIR: one small file per page, written by the
Lua filter during that page's own render from Quarto's own
quarto.doc.output_file. They're never guessed from a naming convention.

Also bakes per-node colors for every color scheme (built-in + user) into
graph.json, from the project's `quarto-graph: color:` config. graph.js
picks node.colors[activeScheme] at widget render time; it holds no palette
logic of its own.
"""

import json
from pathlib import Path, PurePosixPath

from .core import (
    PAGES_DIR,
    REGISTRY_PATH,
    compute_bucket,
    read_project_config,
    resolve_schemes,
)
from .palettes import DEFAULT_COLOR, assign_bucket_colors


def _sort_bucket_key(bucket):
    """Sort legend buckets: ints numerically, strings alphabetically."""
    return (0, bucket) if isinstance(bucket, int) else (1, str(bucket))


def _legend(bucket_colors):
    """Legend array [{bucket, color}...] from a {bucket: hex} map, sorted.
    Buckets are ints for depth schemes, strings otherwise."""
    return [
        {"bucket": bucket, "color": color}
        for bucket, color in sorted(bucket_colors.items(), key=lambda kv: _sort_bucket_key(kv[0]))
    ]


def _scheme_bucket_colors(scheme, rels):
    """Compute {bucket: color} for one scheme across all page rels.
    - folder/custom: bucket = top-level folder (or ROOT_BUCKET)
    - depth: bucket = path depth int
    - custom: exact map; unspecified buckets stay unmapped"""
    by = scheme["by"]
    if by == "custom":
        return dict(scheme["custom"])

    buckets = [compute_bucket(PurePosixPath(rel), by) for rel in rels]
    unique = sorted(set(buckets), key=_sort_bucket_key)
    return assign_bucket_colors(unique, scheme["palette"])


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

    project_config = read_project_config(project_root)
    scheme_info = resolve_schemes(project_config["color"])
    scheme_configs = scheme_info["schemes"]
    scheme_names = sorted(scheme_configs)
    bucket_colors = {
        name: _scheme_bucket_colors(scheme_configs[name], rels)
        for name in scheme_names
    }

    nodes = []
    for rel in rels:
        bucket = compute_bucket(PurePosixPath(rel), "folder")
        depth = compute_bucket(PurePosixPath(rel), "depth")
        colors = {}
        for name in scheme_names:
            by = scheme_configs[name]["by"]
            key = depth if by == "depth" else bucket
            colors[name] = bucket_colors[name].get(key, DEFAULT_COLOR)
        nodes.append({
            "rel": rel,
            "title": registry["pages"][rel]["title"],
            "bucket": bucket,
            "depth": depth,
            "colors": colors,
            "url": output_urls.get(rel, ""),
        })
    edges = sorted(set(
        (min(index[target], index[src["rel"]]), max(index[target], index[src["rel"]]))
        for target, sources in registry["backlinks"].items()
        for src in sources
        if target in index and src["rel"] in index
    ))
    payload = {
        "nodes": nodes,
        "edges": [list(e) for e in edges],
        "schemes": {
            name: {
                "by": scheme_configs[name]["by"],
                "palette": scheme_configs[name]["palette"],
                "legend": _legend(bucket_colors[name]),
            }
            for name in scheme_names
        },
        "default-scheme": scheme_info["default"],
    }

    output_dir = Path(output_dir)
    (output_dir / "graph.json").write_text(json.dumps(payload), encoding="utf-8")

    for f in page_files:
        f.unlink()

    return payload
