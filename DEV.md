Versioning

```bash
uv version --bump patch #bumps toml
git commit -am "release $(uv version --short)"
git tag "v$(uv version --short)" && git push --follow-tags
```

Then release.yml workflow publishes to pypi - workflow is gated to trigger only on commits with a tag push matching v*

Note, bump -> tag order matters because this ensures tag version matches pyprojecct.toml. if mismatch then pypi will reject.