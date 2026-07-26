# quarto-graph

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Quarto project-type extension: adds Obsidian-style `[[wikilinks]]`,
backlinks, and an interactive graph view to a normal Quarto project. Ported
from the sonomabio wiki's MkDocs-based graph widget.

## Quick start

```sh
pip install -e .
cd example-docs
quarto preview .
```

To use in your own project: `quarto add` this extension, then add
`project: {type: quarto-graph}` and `filters: [quarto-graph]` to your
`_quarto.yml`. See `example-docs/` for the full syntax and frontmatter keys.

## More

- [docs/adr/0001-non-destructive-render-time-resolution.md](docs/adr/0001-non-destructive-render-time-resolution.md)
  — why resolution happens at render time via a Lua filter, not a batch
  pre-generation step
- [AGENTS.md](AGENTS.md) — terminology and scope boundaries, for anyone
  (human or agent) working on this codebase


## next steps

- [x] treat normal markdown links as nodes in graph (currently are ignored)
- [ ] better handle on widget embed (layouts, configuration)
- [ ] publish with GHA
- [ ] nested links - how do we handle folders
- [ ] publish to pip
- [ ] publish to quarto extension distributor
- [ ] test in another project (evaluate the ux for install, and usage)
- [ ] optimize graph widget


# Roadmap

version 1 should have these features:

- the main wikilink feature of connecting links
  - Parse wikilinks based on obsidian inspired syntax
  - Store the data (nodes,edges) necessary to plot as graph
  - Quarto extension to inject graph at runtime
  - support regular markdown links too
  - have a basic graph widget similar to obsidian

Optional nice to haves

- [ ] customization of graph widget
- [x] support backlinks graph data enables automatic backlink injection
- [x] Aliases / naming
- [ ] cli interface -> good for CI, opens the door for more user customization (basically exposing the data without quarto runtime)
- [ ] vscode/positron extension that handles autocomplete? other features?
- [ ] customize colors for the nodes