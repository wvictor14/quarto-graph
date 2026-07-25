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


def test_run_prerender_prints_unresolved_warning_to_stderr(project, capsys):
    run_prerender(project)
    captured = capsys.readouterr()
    assert "WARNING: unresolved wikilink [[Missing Target]] in Home.md" in captured.err
    assert captured.out == ""


def test_run_prerender_quiet_suppresses_warning_and_summary(project, monkeypatch, capsys):
    monkeypatch.setenv("QUARTO_PROJECT_SCRIPT_QUIET", "1")
    run_prerender(project)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_run_prerender_quiet_still_raises_on_strict(project, monkeypatch):
    monkeypatch.setenv("QUARTO_PROJECT_SCRIPT_QUIET", "1")
    with pytest.raises(QuartoGraphError, match="unresolved wikilinks"):
        run_prerender(project, strict=True)


def test_run_prerender_defaults_sidebar_true_with_no_quarto_yml(project):
    payload = run_prerender(project)
    assert payload["pages"]["Home.md"]["sidebar"] == {"enabled": True, "depth": 1}
    assert payload["pages"]["Other Page.md"]["sidebar"] == {"enabled": True, "depth": 1}


def test_run_prerender_sidebar_config(tmp_path):
    _write(tmp_path, "_quarto.yml", "quarto-graph:\n  sidebar: false\n")
    _write(tmp_path, "Home.md", "content\n")
    _write(tmp_path, "Other Page.md", "---\nquarto-graph:\n  sidebar: true\n---\ncontent\n")
    payload = run_prerender(tmp_path)
    assert payload["pages"]["Home.md"]["sidebar"] == {"enabled": False, "depth": 1}
    assert payload["pages"]["Other Page.md"]["sidebar"] == {"enabled": True, "depth": 1}


def test_run_prerender_sidebar_config_page_overrides_project_true_to_false(tmp_path):
    _write(tmp_path, "_quarto.yml", "quarto-graph:\n  sidebar: true\n")
    _write(tmp_path, "Home.md", "---\nquarto-graph:\n  sidebar: false\n---\ncontent\n")
    payload = run_prerender(tmp_path)
    assert payload["pages"]["Home.md"]["sidebar"] == {"enabled": False, "depth": 1}


def test_run_prerender_sidebar_depth_override(tmp_path):
    _write(tmp_path, "_quarto.yml", "quarto-graph:\n  sidebar:\n    depth: 2\n")
    _write(tmp_path, "Home.md", "---\nquarto-graph:\n  sidebar:\n    depth: 3\n---\ncontent\n")
    payload = run_prerender(tmp_path)
    assert payload["pages"]["Home.md"]["sidebar"] == {"enabled": True, "depth": 3}


def test_run_prerender_scans_whole_project_regardless_of_a_partial_render(project):
    # Confirmed empirically: QUARTO_PROJECT_INPUT_FILES lists only the
    # file(s) in *this* render invocation -- empty on a `quarto preview`
    # session's own initial pass, or just the one file for a single-file
    # `quarto render`/`quarto preview` -- never reliably "every page in the
    # project," which is what the registry actually needs.
    payload = run_prerender(project)
    assert set(payload["pages"]) == {"Home.md", "Other Page.md"}
