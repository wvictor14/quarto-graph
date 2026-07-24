# Non-destructive, render-time wikilink resolution — no generated files

The original design (ported from an internal Obsidian-vault-to-MkDocs
pipeline) read a separate `vault/` directory of plain Markdown and
generated a parallel `.qmd` tree for Quarto to render, computing each
page's output URL itself. With no separate vault — wikilinks now resolve
directly in a project's own existing `.qmd` pages — rewriting those pages
in place was the obvious alternative, and was rejected: a wikilink resolved
once by overwriting the source loses the wikilink itself (a rename of the
target later has nothing left to re-resolve against), and it turns every
render into a diff against version control.

Decided instead: pre-render builds a registry (titles, `also-known-as`
names, backlinks) once across every page Quarto would already render, and
hands it to a Lua filter that resolves `[[wikilinks]]` and injects
backlinks into the Pandoc AST at each page's own render time — the `.qmd`
source is never rewritten. The same principle extends to URLs: wikilink
hrefs are left as relative links to the target's source path and resolved
by Quarto's own project link rewriting, not computed by this project;
`graph.json` (which a browser navigates, outside Quarto's link rewriting)
is assembled from each page's own real output path after it renders,
rather than predicted from an output-path convention. This project
computes no output paths of its own — the old pipeline's guess at Quarto's
naming convention was the root cause of a real 404 bug (see the vault-era
`Pretty URLs` writeup), and the new design removes the guess entirely
rather than fixing the guess.
