from pathlib import Path, PurePosixPath

from quarto_graph.core import (
    anchor_slug,
    build_backlinks,
    build_registry,
    find_wikilinks_outside_fences,
    normalize_ws,
    parse_page,
    resolve_markdown_href,
)


# --- normalize_ws ------------------------------------------------------------

def test_normalize_ws_collapses_internal_whitespace_and_newlines():
    assert normalize_ws("foo\n  bar\tbaz") == "foo bar baz"


def test_normalize_ws_strips_ends():
    assert normalize_ws("  spaced out  ") == "spaced out"


# --- anchor_slug -------------------------------------------------------------

def test_anchor_slug_strips_punctuation_and_dashes_spaces():
    assert anchor_slug("Section 1: Overview!") == "section-1-overview"


# --- parse_page --------------------------------------------------------------

def test_parse_page_reads_frontmatter_and_title(tmp_path):
    f = tmp_path / "Note.md"
    f.write_text(
        "---\ntitle: Custom Title\nalso-known-as:\n  - Alt Name\n---\nbody text\n",
        encoding="utf-8",
    )
    page = parse_page(f, tmp_path)
    assert page["title"] == "Custom Title"
    assert page["meta"]["also-known-as"] == ["Alt Name"]
    assert page["body"] == "body text\n"
    assert page["rel"] == PurePosixPath("Note.md")


def test_parse_page_no_frontmatter_falls_back_to_stem(tmp_path):
    f = tmp_path / "Plain Page.md"
    f.write_text("just body\n", encoding="utf-8")
    page = parse_page(f, tmp_path)
    assert page["title"] == "Plain Page"
    assert page["meta"] == {}
    assert page["body"] == "just body\n"


def test_parse_page_bad_yaml_frontmatter_warns_and_continues(tmp_path, capsys):
    f = tmp_path / "Bad.md"
    f.write_text("---\nkey: [unterminated\n---\nbody\n", encoding="utf-8")
    page = parse_page(f, tmp_path)
    assert page["meta"] == {}
    assert "WARNING: bad frontmatter" in capsys.readouterr().err


def test_parse_page_reads_type(tmp_path):
    f = tmp_path / "Note.md"
    f.write_text("---\ntype: Concept\n---\nbody\n", encoding="utf-8")
    page = parse_page(f, tmp_path)
    assert page["type"] == "concept"


# --- build_registry -----------------------------------------------------------

def _page(stem, also_known_as=None, rel=None):
    meta = {}
    if also_known_as is not None:
        meta["also-known-as"] = also_known_as
    return {
        "src": Path(stem + ".md"),
        "rel": PurePosixPath(rel or (stem + ".md")),
        "body": "",
        "meta": meta,
        "title": stem,
        "type": "",
    }


def test_build_registry_registers_stem_case_insensitively():
    p = _page("MyPage")
    registry = build_registry([p])
    assert registry["mypage"] is p


def test_build_registry_registers_also_known_as_list():
    p = _page("Real Name", also_known_as=["Alias One", "Alias Two"])
    registry = build_registry([p])
    assert registry["alias one"] is p
    assert registry["alias two"] is p


def test_build_registry_registers_single_string_also_known_as():
    p = _page("Real Name", also_known_as="Solo Alias")
    registry = build_registry([p])
    assert registry["solo alias"] is p


def test_build_registry_duplicate_target_keeps_first_and_warns(capsys):
    first = _page("Dup", rel="a/Dup.md")
    second = _page("Dup", rel="b/Dup.md")
    registry = build_registry([first, second])
    assert registry["dup"] is first
    assert "WARNING: duplicate link target" in capsys.readouterr().err


def test_build_registry_registers_by_title_not_just_filename_stem():
    # A real Quarto project commonly names every source file "index.qmd"
    # inside a slug-named folder -- the filename stem alone ("index") is
    # useless as a default wikilink target, so the page's own `title:`
    # (independent of what the file is actually named) has to work too.
    p = {
        "src": Path("index.md"),
        "rel": PurePosixPath("getting-started/index.md"),
        "body": "",
        "meta": {},
        "title": "Getting Started",
        "type": "",
    }
    registry = build_registry([p])
    assert registry["getting started"] is p


# --- build_backlinks -----------------------------------------------------------

def _body_page(stem, body, also_known_as=None, rel=None):
    page = _page(stem, also_known_as=also_known_as, rel=rel)
    page["body"] = body
    return page


def test_build_backlinks_records_resolved_link():
    home = _body_page("Home", "See [[Other]].\n")
    other = _body_page("Other", "content\n")
    registry = build_registry([home, other])
    backlinks, unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]
    assert unresolved == []


def test_build_backlinks_records_unresolved_with_position():
    home = _body_page("Home", "line one\n[[Missing Target]] on line two\n")
    registry = build_registry([home])
    _backlinks, unresolved = build_backlinks([home], registry)
    assert len(unresolved) == 1
    item = unresolved[0]
    assert item["page"] is home
    assert item["line"] == 2
    assert item["target"] == "Missing Target"


def test_build_backlinks_self_link_not_recorded():
    home = _body_page("Home", "See [[Home]] itself.\n")
    registry = build_registry([home])
    backlinks, _unresolved = build_backlinks([home], registry)
    assert backlinks == {}


def test_build_backlinks_dedupes_repeated_link_from_same_page():
    home = _body_page("Home", "[[Other]] and [[Other]] again.\n")
    other = _body_page("Other", "content\n")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


def test_build_backlinks_resolves_also_known_as():
    home = _body_page("Home", "[[Alias Name]]\n")
    other = _body_page("Other", "content\n", also_known_as=["Alias Name"])
    registry = build_registry([home, other])
    backlinks, unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]
    assert unresolved == []


def test_build_backlinks_records_markdown_link_to_other_page():
    home = _body_page("Home", "See [Other](Other.md).\n")
    other = _body_page("Other", "content\n")
    registry = build_registry([home, other])
    backlinks, unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]
    assert unresolved == []


def test_build_backlinks_markdown_link_with_fragment_resolves():
    home = _body_page("Home", "See [Other](Other.md#some-heading).\n")
    other = _body_page("Other", "content\n")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


def test_build_backlinks_markdown_link_resolves_nested_relative_path():
    home = _body_page("Home", "See [Other](../Other.md).\n", rel="sub/Home.md")
    other = _body_page("Other", "content\n", rel="Other.md")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


def test_build_backlinks_markdown_link_self_link_not_recorded():
    home = _body_page("Home", "See [Home](Home.md) itself.\n")
    registry = build_registry([home])
    backlinks, _unresolved = build_backlinks([home], registry)
    assert backlinks == {}


def test_build_backlinks_ignores_external_and_asset_and_unmatched_markdown_links():
    home = _body_page(
        "Home",
        "[ext](https://example.com/page) "
        "[mail](mailto:a@example.com) "
        "[img](image.png) "
        "[missing](DoesNotExist.md)\n",
    )
    registry = build_registry([home])
    backlinks, unresolved = build_backlinks([home], registry)
    assert backlinks == {}
    assert unresolved == []


def test_build_backlinks_markdown_link_resolves_bare_href_with_space():
    # Pandoc accepts an unescaped space in a bare destination (confirmed via
    # `pandoc -f markdown -t html`, contrary to strict CommonMark), so
    # quarto-graph needs to resolve it the same way.
    home = _body_page("Home", "See [Other](My Other.md).\n")
    other = _body_page("Other", "content\n", rel="My Other.md")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


def test_build_backlinks_markdown_link_resolves_angle_bracket_href():
    home = _body_page("Home", "See [Other](<My Other.md>).\n")
    other = _body_page("Other", "content\n", rel="My Other.md")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


def test_build_backlinks_dedupes_wikilink_and_markdown_link_to_same_target():
    home = _body_page("Home", "[[Other]] and [Other](Other.md) again.\n")
    other = _body_page("Other", "content\n")
    registry = build_registry([home, other])
    backlinks, _unresolved = build_backlinks([home, other], registry)
    assert backlinks[other["rel"]] == [home]


# --- resolve_markdown_href -------------------------------------------------------

def test_resolve_markdown_href_relative_to_same_directory():
    assert resolve_markdown_href(PurePosixPath("Home.md"), "Other.md") == PurePosixPath("Other.md")


def test_resolve_markdown_href_root_relative():
    assert resolve_markdown_href(PurePosixPath("sub/Home.md"), "/Other.md") == PurePosixPath("Other.md")


def test_resolve_markdown_href_rejects_external_scheme_and_protocol_relative():
    assert resolve_markdown_href(PurePosixPath("Home.md"), "https://example.com/x") is None
    assert resolve_markdown_href(PurePosixPath("Home.md"), "//example.com/x") is None
    assert resolve_markdown_href(PurePosixPath("Home.md"), "mailto:a@example.com") is None


def test_resolve_markdown_href_fragment_only_is_none():
    assert resolve_markdown_href(PurePosixPath("Home.md"), "#heading") is None


# --- find_wikilinks_outside_fences ----------------------------------------------

def test_find_wikilinks_outside_fences_reports_line_and_col():
    text = "no link here\n[[Target]] at start of line two\n"
    hits = find_wikilinks_outside_fences(text)
    assert len(hits) == 1
    line, col, match = hits[0]
    assert line == 2
    assert col == 1
    assert match.group(1) == "Target"


def test_find_wikilinks_outside_fences_skips_fenced_links():
    text = "```\n[[Fenced]]\n```\n[[Real]]\n"
    hits = find_wikilinks_outside_fences(text)
    assert len(hits) == 1
    assert hits[0][2].group(1) == "Real"


def test_find_wikilinks_outside_fences_multiple_on_same_line():
    text = "[[One]] and [[Two]]\n"
    hits = find_wikilinks_outside_fences(text)
    assert [h[2].group(1) for h in hits] == ["One", "Two"]
    assert hits[0][1] == 1
    assert hits[1][1] == text.index("[[Two]]") + 1


def test_find_wikilinks_outside_fences_matches_target_wrapped_across_hard_linebreak():
    # War story: an earlier fix processed one physical line at a time, which
    # broke any wikilink target that happens to hard-wrap across a line
    # inside a paragraph (very normal hand-wrapped prose).
    text = "See [[Some Long\nTarget Name]] for more."
    hits = find_wikilinks_outside_fences(text)
    assert len(hits) == 1
    assert normalize_ws(hits[0][2].group(1)) == "Some Long Target Name"
