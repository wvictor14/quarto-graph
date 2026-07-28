Versioning

There is versioning for the quarto extension `_extension.yml` and then versioning
for the python package. They are not necessarily in sync.

# Quarto extension

Manually bump the version in `_extension.yml`

# Python package

```bash
uv version --bump minor #bumps toml
git commit -am "release $(uv version --short)"
git tag "v$(uv version --short)" && git push --follow-tags
```

Then release.yml workflow publishes to pypi - workflow is gated to trigger only on commits with a tag push matching v*

Note, bump -> tag order matters because this ensures tag version matches pyprojecct.toml. if mismatch then pypi will reject.

Test:

```bash
uv run --with quarto-graph --no-project -- python -c "import quarto_graph; print(quarto_graph.__version__)"
```