from quarto_graph.check import check_links, discover_pages


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_check_links_writes_nothing(tmp_path):
    _write(tmp_path, "Home.md", "[[Missing]]\n")
    before = set(tmp_path.rglob("*"))
    check_links(tmp_path)
    after = set(tmp_path.rglob("*"))
    assert before == after


def test_check_links_reports_unresolved_with_position(tmp_path):
    _write(tmp_path, "Home.md", "line one\n[[Missing Target]] on line two\n")
    problems = check_links(tmp_path)
    assert len(problems) == 1
    p = problems[0]
    assert p["file"] == "Home.md"
    assert p["line"] == 2
    assert p["col"] == 1
    assert p["target"] == "Missing Target"


def test_check_links_resolved_link_not_reported(tmp_path):
    _write(tmp_path, "Home.md", "[[Other]]\n")
    _write(tmp_path, "Other.md", "content\n")
    assert check_links(tmp_path) == []


def test_check_links_resolves_also_known_as(tmp_path):
    _write(tmp_path, "Home.md", "[[Alias Name]]\n")
    _write(tmp_path, "Other.md", "---\nalso-known-as:\n  - Alias Name\n---\ncontent\n")
    assert check_links(tmp_path) == []


def test_check_links_ignores_fenced_wikilinks(tmp_path):
    _write(tmp_path, "Home.md", "```\n[[Not A Real Link]]\n```\n")
    assert check_links(tmp_path) == []


# --- discover_pages ------------------------------------------------------------

def test_discover_pages_finds_qmd_and_md(tmp_path):
    _write(tmp_path, "Home.md", "content\n")
    _write(tmp_path, "other.qmd", "content\n")
    pages = discover_pages(tmp_path)
    assert {p["title"] for p in pages} == {"Home", "other"}


def test_discover_pages_skips_dot_and_underscore_dirs(tmp_path):
    _write(tmp_path, "Visible.md", "content\n")
    _write(tmp_path, ".hidden/Secret.md", "content\n")
    _write(tmp_path, "_extensions/quarto-graph/Skip.md", "content\n")
    _write(tmp_path, "_site/Built.md", "content\n")
    pages = discover_pages(tmp_path)
    assert [p["title"] for p in pages] == ["Visible"]


def test_discover_pages_empty_project_returns_empty(tmp_path):
    assert discover_pages(tmp_path) == []
