# quarto-graph

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Quarto project-type extension: adds Obsidian-style `[[wikilinks]]`,
backlinks, and an interactive graph view to a normal Quarto project.

## Quick start

Install the python package

```sh
pip install -e quarto-graph
```

Install quarto, and then the extension

```sh
quarto add wvictor14/quarto-graph

# Run example
quarto preview example-docs
```

To use in your own project: `quarto add` this extension, then add this to
your `_quarto.yml`:

```yaml
project:
  type: website
  pre-render: quarto-graph prerender
  post-render: quarto-graph postrender

filters:
  - quarto-graph
```

See `example-docs/` for the full syntax and frontmatter keys.

## next steps

- [x] treat normal markdown links as nodes in graph (currently are ignored)
- [x] better handle on widget embed (layouts, configuration)
- [x] publish with GHA
- [x] nested links - how do we handle folders
- [x] publish to pip
- [x] publish to quarto extension distributor (it's just github I guess)
- [ ] test in another project (evaluate the ux for install, and usage) {.in-progress}
- [ ] more fully flesh out cli
  - explore what can be done with exposed graph data e.g. in an analysis or dashboard

# Roadmap

version 1 should have these features:

- the main wikilink feature of connecting links
  - Parse wikilinks based on obsidian inspired syntax
  - Store the data (nodes,edges) necessary to plot as graph
  - Quarto extension to inject graph at runtime
  - support regular markdown links too
  - have a basic graph widget similar to obsidian

Optional nice to haves

- [x] customization of graph widget
- [x] support backlinks graph data enables automatic backlink injection
- [x] Aliases / naming
- [ ] cli interface -> good for CI, opens the door for more user customization (basically exposing the data without quarto runtime)
  - complication: render / target resolves currently depend on quarto runtime (relies on quarto's resolver), meaning standalone cli would need to add quarto dependency for exact behaviour matching.
  - Sort of done, but could be more fully fleshed out including docs
- [ ] vscode/positron extension that handles autocomplete? other features?
- [ ] customize colors for the nodes


# Limitations

Quarto preview with --output-dir (default command on positron "preview" function) errors.