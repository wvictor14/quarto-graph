"""quarto-graph CLI: `check` (read-only unresolved-link diagnostics, for
editor tooling), plus `prerender`/`postrender`, which a consuming project's
own `_quarto.yml` wires up directly as `pre-render`/`post-render` commands
(both run with cwd already set to the project root by Quarto)."""

import argparse
import json
import os
import sys
from pathlib import Path

from .check import check_links
from .postrender import run_postrender
from .prerender import QuartoGraphError, run_prerender


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="quarto-graph")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="Report unresolved wikilinks as JSON; writes nothing")
    check_p.add_argument("project_dir")

    prerender_p = sub.add_parser("prerender", help="Build the wikilink/backlink registry (run as a Quarto pre-render hook)")
    prerender_p.add_argument("--strict", action="store_true", help="Fail if any wikilink is unresolved")

    sub.add_parser("postrender", help="Assemble graph.json from the registry (run as a Quarto post-render hook)")

    args = parser.parse_args(argv)

    if args.command == "check":
        problems = check_links(Path(args.project_dir))
        print(json.dumps(problems))
    elif args.command == "prerender":
        try:
            run_prerender(Path.cwd(), strict=args.strict)
        except QuartoGraphError as exc:
            sys.exit("ERROR: {}".format(exc))
    elif args.command == "postrender":
        output_dir = Path.cwd() / os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site")
        run_postrender(Path.cwd(), output_dir)


if __name__ == "__main__":
    main()
