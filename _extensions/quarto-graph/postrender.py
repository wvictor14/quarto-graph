#!/usr/bin/env python3
"""Thin shim: delegates to the installed `quarto-graph` package. Assembles
graph.json from the registry prerender.py wrote and each page's own real
output path, which the Lua filter records during that page's own render.

Quarto invokes this via project.post-render with the working directory
already set to the project root, and QUARTO_PROJECT_OUTPUT_DIR naming the
real output directory.

Usage: postrender.py
"""

import os
import sys
from pathlib import Path

try:
    from quarto_graph.postrender import run_postrender
except ImportError:
    sys.exit(
        "ERROR: the 'quarto-graph' package is not installed in this Python "
        "environment. Run `pip install -e .` from the repo root."
    )

if __name__ == "__main__":
    output_dir = Path.cwd() / os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site")
    run_postrender(Path.cwd(), output_dir)
