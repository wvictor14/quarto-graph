"""quarto-graph CLI: `check` (read-only unresolved-link diagnostics, for
editor tooling). Pre-render/post-render are invoked by Quarto directly
through the extension's own shim scripts, not through this CLI."""

import argparse
import json
import sys
from pathlib import Path

from .check import check_links


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="quarto-graph")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="Report unresolved wikilinks as JSON; writes nothing")
    check_p.add_argument("project_dir")

    args = parser.parse_args(argv)

    if args.command == "check":
        problems = check_links(Path(args.project_dir))
        print(json.dumps(problems))


if __name__ == "__main__":
    main()
