Versioning

There is versioning for the quarto extension `_extension.yml` and then versioning
for the python package. They are released together, one command bumps both.

```bash
uv version --bump minor #bumps toml
sed -i "s/^version: .*/version: $(uv version --short)/" _extensions/quarto-graph/_extension.yml
git commit -am "release $(uv version --short)"
git tag "v$(uv version --short)" && git push --follow-tags
```

Then release.yml workflow publishes to pypi - workflow is gated to trigger only on commits with a tag push matching v*. Not yet exercised end to end (no release has been published to pypi yet, and pypi trusted publishing isn't confirmed configured for this project) - verify on the first real release.

Note, bump -> tag order matters because this ensures tag version matches pyprojecct.toml. if mismatch then pypi will reject.

`quarto_graph.__version__` reads from installed package metadata (`importlib.metadata.version("quarto-graph")`), not a hand-maintained string - it always matches `pyproject.toml`, no separate bump step.

Test:

```bash
uv run --with quarto-graph --no-project -- python -c "import quarto_graph; print(quarto_graph.__version__)"
```