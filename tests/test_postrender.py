import json

from quarto_graph.postrender import PAGES_DIR, run_postrender
from quarto_graph.prerender import run_prerender


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(root, rel, obj):
    _write(root, rel, json.dumps(obj))


def test_run_postrender_assembles_graph_with_dedup_edges(tmp_path):
    _write(tmp_path, "Home.md", "Welcome. See [[Other Page]].\n")
    _write(tmp_path, "Other Page.md", "Back to [[Home]].\n")
    run_prerender(tmp_path)

    _write_json(tmp_path, PAGES_DIR / "home.json", {"rel": "Home.md", "output_url": "home.html"})
    _write_json(tmp_path, PAGES_DIR / "other-page.json", {"rel": "Other Page.md", "output_url": "other-page.html"})

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    assert {n["title"] for n in payload["nodes"]} == {"Home", "Other Page"}
    urls = {n["title"]: n["url"] for n in payload["nodes"]}
    assert urls["Home"] == "home.html"
    assert urls["Other Page"] == "other-page.html"
    # Home <-> Other Page is a mutual link; must be one deduped edge, not two.
    assert payload["edges"] == [[0, 1]]
    on_disk = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
    assert on_disk == payload


def test_run_postrender_cleans_up_per_page_files(tmp_path):
    _write(tmp_path, "Home.md", "content\n")
    run_prerender(tmp_path)
    _write_json(tmp_path, PAGES_DIR / "home.json", {"rel": "Home.md", "output_url": "home.html"})

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    run_postrender(tmp_path, out_dir)

    assert list((tmp_path / PAGES_DIR).glob("*.json")) == []


def test_run_postrender_missing_output_url_defaults_empty(tmp_path):
    _write(tmp_path, "Home.md", "content\n")
    run_prerender(tmp_path)

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    assert payload["nodes"] == [{"title": "Home", "type": "", "url": ""}]
