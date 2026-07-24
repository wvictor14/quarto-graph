#!/usr/bin/env python3
"""Thin shim: delegates to the installed `quarto-graph` package (see
src/quarto_graph at the repo root) so this extension's pre-render step and
any editor tooling share exactly one implementation of wikilink/alias
resolution, instead of two.

Quarto invokes this via project.pre-render with the working directory
already set to the project root.

Requires `pip install -e .` (or a published release) into whatever Python
`quarto render` invokes.

Usage: prerender.py [--strict]
"""

import sys
from pathlib import Path

try:
    from quarto_graph.prerender import QuartoGraphError, run_prerender
except ImportError:
    sys.exit(
        "ERROR: the 'quarto-graph' package is not installed in this Python "
        "environment. Run `pip install -e .` from the repo root."
    )

if __name__ == "__main__":
    try:
        run_prerender(Path.cwd(), strict="--strict" in sys.argv[1:])
    except QuartoGraphError as exc:
        sys.exit("ERROR: {}".format(exc))
