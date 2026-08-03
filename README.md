# quarto-graph

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.4.0-blue)](pyproject.toml)
[![Lifecycle](https://img.shields.io/badge/lifecycle-early%20development-orange)](https://github.com/wvictor14/quarto-graph)

Quarto project-type extension: adds Obsidian-style `[[wikilinks]]`,
backlinks, and an interactive graph view to a normal Quarto project.

## Status

Early development, pre-1.0. API and behavior may change between releases.

## Quick start

Install the python package

```sh
pip install quarto-graph
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

See the [documentation site](https://victoryuan.com/quarto-graph/news/) for the full syntax and frontmatter keys.

## Node colors

By default every node is colored by its top-level folder using the
Okabe-Ito colorblind-safe palette, so a project organized by topic folder
shows those structural groups at a glance. Configure via
`quarto-graph: color:` in `_quarto.yml`:

```yaml
quarto-graph:
  color:
    default-scheme: my-pal
    schemes:
      by-folder: {by: folder, palette: okabe-ito}   # the default
      by-depth:  {by: depth, palette: viridis}      # nesting depth shades
      my-pal:
        by: custom
        custom:
          concepts: "#ee7733"
          reference: "#0077bb"
```

Pick a scheme per widget without touching config:

```markdown
{{< quarto-graph-full color-scheme="by-depth" >}}
```

Built-in schemes: `by-folder` (default) and `by-depth`. Palettes:
`okabe-ito`, `d3-category10`, `viridis`; auto-generated colors kick in
when folders outnumber a qualitative palette. See the docs site for the
full reference.

## next steps

- [ ] test in another project (evaluate the ux for install, and usage) {.in-progress}
- [ ] graph configuration
  - [ ] classes
  - [x] node colors
  - [ ] default appearance (font size, zoom)
- [ ] more fully flesh out cli 
  - explore what can be done with exposed graph data e.g. in an analysis or dashboard
- [ ] backlinks should be configurable on/off, as well as header and heading level

# Roadmap

version 1 should have these features:

- resolve links between pages using either wikilink, link syntax
- support aliases
- basic graph widget with basic customization
- backlinks
- installable from pip / quarto add

Optional nice to haves

- [ ] vscode/positron extension that handles autocomplete and syntax highlighting.
- [ ] customize colors for the nodes and links. Quartz has a nice visual on edge directionality
- [ ] filterable graph? e.g. restrict graph to certain folders or node types?

# Limitations & Bugs

Quarto preview with --output-dir (default command on positron "preview" function) errors.