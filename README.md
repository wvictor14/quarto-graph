# quarto-graph

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

- [ ] treat normal markdown links as nodes in graph (currently are ignored)
- [ ] publish with GHA
- [ ] test in another project (evaluate the ux for install, and usage)
- [ ] optimize graph widget