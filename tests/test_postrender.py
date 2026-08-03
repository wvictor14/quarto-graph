import json

from quarto_graph.core import PAGES_DIR
from quarto_graph.postrender import run_postrender
from quarto_graph.prerender import run_prerender


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(root, rel, obj):
    _write(root, rel, json.dumps(obj))


def _write_output_urls(root, rels):
    for rel in rels:
        safe = rel.replace("/", "_").replace(".", "_")
        _write_json(root, PAGES_DIR / f"{safe}.json", {"rel": rel, "output_url": rel + ".html"})


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

    node = payload["nodes"][0]
    assert node["rel"] == "Home.md"
    assert node["title"] == "Home"
    assert node["url"] == ""
    assert node["bucket"] == "(root)"
    assert node["depth"] == 0
    assert "type" not in node


def test_run_postrender_default_schemes_and_builtin_colors(tmp_path):
    _write(tmp_path, "Home.md", "content\n")
    run_prerender(tmp_path)
    _write_output_urls(tmp_path, ["Home.md"])

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    assert payload["default-scheme"] == "by-folder"
    assert set(payload["schemes"]) == {"by-folder", "by-depth"}
    # Single root page: folder scheme starts at Okabe-Ito orange; depth
    # scheme at viridis dark purple, and every node color is keyed by scheme.
    node = payload["nodes"][0]
    assert node["colors"]["by-folder"] == "#e69f00"
    assert node["colors"]["by-depth"] == "#440154"
    legend = payload["schemes"]["by-folder"]["legend"]
    assert legend == [{"bucket": "(root)", "color": "#e69f00"}]


def test_run_postrender_folder_buckets_per_top_level_folder(tmp_path):
    _write(tmp_path, "concepts/a.md", "content\n")
    _write(tmp_path, "reference/b.md", "content\n")
    _write(tmp_path, "Home.md", "content\n")
    run_prerender(tmp_path)
    _write_output_urls(tmp_path, ["concepts/a.md", "reference/b.md", "Home.md"])

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    by_bucket = {n["title"]: n["bucket"] for n in payload["nodes"]}
    assert by_bucket == {"a": "concepts", "b": "reference", "Home": "(root)"}
    # Alphabetical buckets -> palette order, expect three distinct colors.
    colors = {n["colors"]["by-folder"] for n in payload["nodes"]}
    assert colors == {"#e69f00", "#56b4e9", "#009e73"}


def test_run_postrender_depth_buckets(tmp_path):
    _write(tmp_path, "Main.md", "content\n")
    _write(tmp_path, "a/b/Deep.md", "content\n")
    run_prerender(tmp_path)
    _write_output_urls(tmp_path, ["Main.md", "a/b/Deep.md"])

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    by_bucket = {n["title"]: n["depth"] for n in payload["nodes"]}
    assert by_bucket == {"Main": 0, "Deep": 2}
    legend = payload["schemes"]["by-depth"]["legend"]
    assert legend == [{"bucket": 0, "color": "#440154"}, {"bucket": 2, "color": "#fde725"}]


def test_run_postrender_custom_scheme_bakes_exact_colors(tmp_path):
    _write(tmp_path, "_quarto.yml", (
        "quarto-graph:\n"
        "  color:\n"
        "    default-scheme: my-pal\n"
        "    schemes:\n"
        "      my-pal:\n"
        "        by: custom\n"
        "        custom:\n"
        "          concepts: '#ee7733'\n"
    ))
    _write(tmp_path, "concepts/x.md", "content\n")
    _write(tmp_path, "reference/y.md", "content\n")
    run_prerender(tmp_path)
    _write_output_urls(tmp_path, ["concepts/x.md", "reference/y.md"])

    out_dir = tmp_path / "_site"
    out_dir.mkdir()
    payload = run_postrender(tmp_path, out_dir)

    assert payload["default-scheme"] == "my-pal"
    by_title = {n["title"]: n["colors"]["my-pal"] for n in payload["nodes"]}
    # concepts mapped; reference unmapped in the custom map -> default gray.
    assert by_title == {"x": "#ee7733", "y": "#9aa0a6"}
    legend = payload["schemes"]["my-pal"]["legend"]
    assert legend == [{"bucket": "concepts", "color": "#ee7733"}]
