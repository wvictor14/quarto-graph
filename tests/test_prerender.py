import json

import pytest

from quarto_graph.prerender import QuartoGraphError, REGISTRY_PATH, run_prerender


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path):
    _write(tmp_path, "Home.md", "Welcome. See [[Other Page]] and [[Missing Target]].\n")
    _write(tmp_path, "Other Page.md", "---\nalso-known-as:\n  - Alias Name\n---\nBack to [[Home]].\n")
    return tmp_path


def test_run_prerender_writes_registry_with_resolved_backlinks(project):
    payload = run_prerender(project)
    assert payload["pages"]["Home.md"]["title"] == "Home"
    assert payload["registry"]["other page"] == "Other Page.md"
    assert payload["registry"]["alias name"] == "Other Page.md"
    assert payload["backlinks"]["Other Page.md"] == [{"title": "Home", "rel": "Home.md"}]
    on_disk = json.loads((project / REGISTRY_PATH).read_text(encoding="utf-8"))
    assert on_disk == payload


def test_run_prerender_strict_raises_on_unresolved(project):
    with pytest.raises(QuartoGraphError, match="unresolved wikilinks"):
        run_prerender(project, strict=True)


def test_run_prerender_non_strict_does_not_raise(project):
    run_prerender(project, strict=False)


def test_run_prerender_prints_unresolved_warning(project, capsys):
    run_prerender(project)
    out = capsys.readouterr().out
    assert "WARNING: unresolved wikilink [[Missing Target]] in Home.md" in out


def test_run_prerender_scans_whole_project_regardless_of_a_partial_render(project):
    # Confirmed empirically: QUARTO_PROJECT_INPUT_FILES lists only the
    # file(s) in *this* render invocation -- empty on a `quarto preview`
    # session's own initial pass, or just the one file for a single-file
    # `quarto render`/`quarto preview` -- never reliably "every page in the
    # project," which is what the registry actually needs.
    payload = run_prerender(project)
    assert set(payload["pages"]) == {"Home.md", "Other Page.md"}
