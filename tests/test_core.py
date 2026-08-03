from pathlib import Path, PurePosixPath

import pytest

from quarto_graph.core import (
    anchor_slug,
    build_backlinks,
    build_registry,
    compute_bucket,
    discover_paths,
    find_wikilinks_outside_fences,
    identifier_chain,
    normalize_ws,
    page_sidebar_config,
    parse_page,
    read_project_config,
    resolve_markdown_href,
    resolve_schemes,
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


def test_parse_page_does_not_parse_type(tmp_path):
    # `type:` is an Obsidian skeleton from an older version, deliberately
    # unsupported now (AGENTS.md categories note). parse_page must not
    # surface it.
    f = tmp_path / "Note.md"
    f.write_text("---\ntype: Concept\n---\nbody\n", encoding="utf-8")
    page = parse_page(f, tmp_path)
    assert "type" not in page


# --- compute_bucket ------------------------------------------------------------

def test_compute_bucket_folder_top_level():
    assert compute_bucket(PurePosixPath("concepts/backlinks/index.qmd"), "folder") == "concepts"


def test_compute_bucket_folder_nested_uses_top_level():
    assert compute_bucket(PurePosixPath("a/b/c/page.md"), "folder") == "a"


def test_compute_bucket_folder_root_pages_use_root_bucket():
    assert compute_bucket(PurePosixPath("index.qmd"), "folder") == "(root)"


def test_compute_bucket_depth_counts_parent_dirs():
    assert compute_bucket(PurePosixPath("index.qmd"), "depth") == 0
    assert compute_bucket(PurePosixPath("getting-started/index.qmd"), "depth") == 1
    assert compute_bucket(PurePosixPath("concepts/backlinks/index.qmd"), "depth") == 2


# --- resolve_schemes -----------------------------------------------------------

def test_resolve_schemes_defaults_to_builtins():
    result = resolve_schemes({})
    assert result["default"] == "by-folder"
    assert set(result["schemes"]) == {"by-folder", "by-depth"}
    assert result["schemes"]["by-folder"]["by"] == "folder"
    assert result["schemes"]["by-depth"]["palette"] == "viridis"


def test_resolve_schemes_user_scheme_and_override_default():
    result = resolve_schemes({
        "default-scheme": "my-pal",
        "schemes": {"my-pal": {"by": "custom", "custom": {"concepts": "#ee7733"}}},
    })
    assert result["default"] == "my-pal"
    assert "my-pal" in result["schemes"]
    assert result["schemes"]["my-pal"]["custom"] == {"concepts": "#ee7733"}
    assert result["schemes"]["by-folder"]["by"] == "folder"


def test_resolve_schemes_user_overrides_builtin():
    result = resolve_schemes({"schemes": {"by-folder": {"by": "folder", "palette": "d3-category10"}}})
    assert result["schemes"]["by-folder"]["palette"] == "d3-category10"


def test_resolve_schemes_bad_palette_warns_and_defaults(capsys):
    result = resolve_schemes({"schemes": {"odd": {"by": "folder", "palette": "nope"}}})
    assert result["schemes"]["odd"]["palette"] == "okabe-ito"
    assert "WARNING: unknown palette name" in capsys.readouterr().err


def test_resolve_schemes_unknown_default_warns_and_uses_by_folder(capsys):
    result = resolve_schemes({"default-scheme": "missing"})
    assert result["default"] == "by-folder"
    assert "WARNING: default-scheme" in capsys.readouterr().err


# --- read_project_config -----------------------------------------------------

def test_read_project_config_missing_file_defaults_true(tmp_path):
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": True, "depth": 1}, "exclude": [], "color": {}}


def test_read_project_config_reads_sidebar_false(tmp_path):
    (tmp_path / "_quarto.yml").write_text("quarto-graph:\n  sidebar: false\n", encoding="utf-8")
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": False, "depth": 1}, "exclude": [], "color": {}}


def test_read_project_config_reads_sidebar_object_with_depth(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "quarto-graph:\n  sidebar:\n    enabled: true\n    depth: 2\n", encoding="utf-8"
    )
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": True, "depth": 2}, "exclude": [], "color": {}}


def test_read_project_config_sidebar_object_missing_depth_defaults_to_one(tmp_path):
    (tmp_path / "_quarto.yml").write_text("quarto-graph:\n  sidebar:\n    enabled: false\n", encoding="utf-8")
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": False, "depth": 1}, "exclude": [], "color": {}}


def test_read_project_config_sidebar_depth_floors_at_one(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "quarto-graph:\n  sidebar:\n    depth: 0\n", encoding="utf-8"
    )
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": True, "depth": 1}, "exclude": [], "color": {}}


def test_read_project_config_no_quarto_graph_key_defaults_true(tmp_path):
    (tmp_path / "_quarto.yml").write_text("project:\n  type: website\n", encoding="utf-8")
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": True, "depth": 1}, "exclude": [], "color": {}}


def test_read_project_config_bad_yaml_warns_and_defaults(tmp_path, capsys):
    (tmp_path / "_quarto.yml").write_text("key: [unterminated\n", encoding="utf-8")
    assert read_project_config(tmp_path) == {"sidebar": {"enabled": True, "depth": 1}, "exclude": [], "color": {}}
    assert "WARNING: bad YAML" in capsys.readouterr().err


def test_read_project_config_reads_exclude_list(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "quarto-graph:\n  exclude:\n    - archive/\n    - \"*.draft.qmd\"\n", encoding="utf-8"
    )
    assert read_project_config(tmp_path)["exclude"] == ["archive/", "*.draft.qmd"]


def test_read_project_config_exclude_not_a_list_warns_and_defaults(tmp_path, capsys):
    (tmp_path / "_quarto.yml").write_text("quarto-graph:\n  exclude: not-a-list\n", encoding="utf-8")
    assert read_project_config(tmp_path)["exclude"] == []
    assert "WARNING: quarto-graph: exclude:" in capsys.readouterr().err


def test_read_project_config_exclude_drops_non_string_entries(tmp_path, capsys):
    (tmp_path / "_quarto.yml").write_text("quarto-graph:\n  exclude:\n    - archive/\n    - 5\n", encoding="utf-8")
    assert read_project_config(tmp_path)["exclude"] == ["archive/"]
    assert "WARNING: ignoring non-string exclude pattern" in capsys.readouterr().err


# --- discover_paths -----------------------------------------------------------

def test_discover_paths_fallback_skips_default_excluded_filenames(tmp_path):
    # No _quarto.yml at all -- fallback branch, must apply the same
    # README/CLAUDE.md/AGENTS.md filtering quarto inspect gives for free in
    # the real-project branch.
    (tmp_path / "Visible.md").write_text("content\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("content\n", encoding="utf-8")
    (tmp_path / "README.qmd").write_text("content\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("content\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("content\n", encoding="utf-8")
    assert [p.name for p in discover_paths(tmp_path)] == ["Visible.md"]


def test_discover_paths_real_project_honors_render_list_negation(tmp_path):
    # Only quarto inspect understands `render:` negation -- this only
    # passes if the quarto-inspect branch actually ran, not the fallback.
    (tmp_path / "_quarto.yml").write_text(
        'project:\n  type: default\n  render:\n    - "*.qmd"\n    - "!drafts/"\n',
        encoding="utf-8",
    )
    (tmp_path / "index.qmd").write_text("content\n", encoding="utf-8")
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / "secret.qmd").write_text("content\n", encoding="utf-8")
    rels = {p.relative_to(tmp_path).as_posix() for p in discover_paths(tmp_path)}
    assert rels == {"index.qmd"}


def test_discover_paths_exclude_directory_prefix(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "project:\n  type: default\nquarto-graph:\n  exclude:\n    - archive/\n", encoding="utf-8"
    )
    (tmp_path / "index.qmd").write_text("content\n", encoding="utf-8")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "old.qmd").write_text("content\n", encoding="utf-8")
    rels = {p.relative_to(tmp_path).as_posix() for p in discover_paths(tmp_path)}
    assert rels == {"index.qmd"}


def test_discover_paths_exclude_glob_pattern(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        'project:\n  type: default\nquarto-graph:\n  exclude:\n    - "*.draft.qmd"\n', encoding="utf-8"
    )
    (tmp_path / "index.qmd").write_text("content\n", encoding="utf-8")
    (tmp_path / "scratch.draft.qmd").write_text("content\n", encoding="utf-8")
    rels = {p.relative_to(tmp_path).as_posix() for p in discover_paths(tmp_path)}
    assert rels == {"index.qmd"}


# --- page_sidebar_config -------------------------------------------------------

def _page_with_meta(meta):
    return {"meta": meta}


# The-graph-widget doc's "mini-panel shows?" table, 1:1 -- each row here is
# that table's row, project sidebar -> page sidebar -> resolved config
# (enabled implies "shows", not enabled implies "no").
@pytest.mark.parametrize(
    "project_sidebar, page_sidebar, expected",
    [
        pytest.param({"enabled": True, "depth": 1}, None, {"enabled": True, "depth": 1}, id="true-unset-yes-depth-1"),
        pytest.param({"enabled": True, "depth": 1}, False, {"enabled": False, "depth": 1}, id="true-false-no"),
        pytest.param({"enabled": False, "depth": 1}, None, {"enabled": False, "depth": 1}, id="false-unset-no"),
        pytest.param({"enabled": False, "depth": 1}, True, {"enabled": True, "depth": 1}, id="false-true-yes-depth-1"),
        pytest.param(
            {"enabled": True, "depth": 2}, {"depth": 3}, {"enabled": True, "depth": 3}, id="depth-2-depth-3-yes-depth-3"
        ),
    ],
)
def test_page_sidebar_config_docs_table(project_sidebar, page_sidebar, expected):
    page_meta = {} if page_sidebar is None else {"quarto-graph": {"sidebar": page_sidebar}}
    assert page_sidebar_config(_page_with_meta(page_meta), {"sidebar": project_sidebar}) == expected


def test_page_sidebar_config_falls_back_to_project_default_true():
    assert page_sidebar_config(_page_with_meta({}), {"sidebar": {"enabled": True, "depth": 1}}) == {
        "enabled": True, "depth": 1,
    }


def test_page_sidebar_config_falls_back_to_project_default_false():
    assert page_sidebar_config(_page_with_meta({}), {"sidebar": {"enabled": False, "depth": 1}}) == {
        "enabled": False, "depth": 1,
    }


def test_page_sidebar_config_page_overrides_project_true_to_false():
    page = _page_with_meta({"quarto-graph": {"sidebar": False}})
    result = page_sidebar_config(page, {"sidebar": {"enabled": True, "depth": 1}})
    assert result == {"enabled": False, "depth": 1}


def test_page_sidebar_config_page_overrides_project_false_to_true():
    page = _page_with_meta({"quarto-graph": {"sidebar": True}})
    result = page_sidebar_config(page, {"sidebar": {"enabled": False, "depth": 1}})
    assert result == {"enabled": True, "depth": 1}


def test_page_sidebar_config_page_depth_only_keeps_project_enabled():
    page = _page_with_meta({"quarto-graph": {"sidebar": {"depth": 2}}})
    result = page_sidebar_config(page, {"sidebar": {"enabled": False, "depth": 1}})
    assert result == {"enabled": False, "depth": 2}


def test_page_sidebar_config_page_enabled_only_keeps_project_depth():
    page = _page_with_meta({"quarto-graph": {"sidebar": {"enabled": False}}})
    result = page_sidebar_config(page, {"sidebar": {"enabled": True, "depth": 3}})
    assert result == {"enabled": False, "depth": 3}


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
    }
    registry = build_registry([p])
    assert registry["getting started"] is p


# --- identifier_chain ---------------------------------------------------------

def test_identifier_chain_folds_index_into_its_folder():
    assert identifier_chain(PurePosixPath("a/b/c/index.md")) == ("a", "b", "c")


def test_identifier_chain_keeps_stem_for_a_non_index_page():
    assert identifier_chain(PurePosixPath("notes/Overview.md")) == ("notes", "Overview")


def test_identifier_chain_keeps_index_for_the_top_level_page():
    # There's only ever one literal index.md/index.qmd at the project root
    # -- nothing to fold it into, and no collision risk from keeping it.
    assert identifier_chain(PurePosixPath("index.md")) == ("index",)


# --- build_registry: index.qmd folder-note resolution --------------------------

def _index_page(rel, title=None):
    rel = PurePosixPath(rel)
    chain = identifier_chain(rel)
    return {
        "src": Path(rel.name),
        "rel": rel,
        "body": "",
        "meta": {"title": title} if title else {},
        "title": title or chain[-1],
    }


def test_build_registry_title_less_index_pages_resolve_by_folder_name():
    page1 = _index_page("page1/index.md")
    page2 = _index_page("page2/index.md")
    registry = build_registry([page1, page2])
    assert registry["page1"] is page1
    assert registry["page2"] is page2


def test_build_registry_bare_index_never_registered_and_warns_nothing(capsys):
    page1 = _index_page("page1/index.md")
    page2 = _index_page("page2/index.md")
    registry = build_registry([page1, page2])
    assert "index" not in registry
    assert capsys.readouterr().err == ""


def test_build_registry_explicit_index_suffix_also_resolves():
    page1 = _index_page("page1/index.md")
    registry = build_registry([page1])
    assert registry["page1/index"] is page1
    assert registry["page1"] is page1


def test_build_registry_ambiguous_folder_name_disambiguated_by_qualified_path(capsys):
    # Two folders both named "api" at different nesting depths: the bare
    # name is a genuine ambiguity (warns once, first wins, unchanged
    # policy), but each is still individually reachable once qualified.
    docs_api = _index_page("docs/api/index.md")
    vendor_api = _index_page("vendor/api/index.md")
    registry = build_registry([docs_api, vendor_api])
    assert registry["api"] is docs_api
    assert "WARNING: duplicate link target" in capsys.readouterr().err
    assert registry["docs/api"] is docs_api
    assert registry["vendor/api"] is vendor_api


def test_build_registry_title_still_qualifiable_by_ancestor_folder(capsys):
    # The "general, not index-only" scope: an explicit title collision
    # (not just a folder-name collision) is also disambiguated by qualifying
    # it with enough of its own path.
    notes = _index_page("notes/index.md", title="Overview")
    projects = _index_page("projects/index.md", title="Overview")
    registry = build_registry([notes, projects])
    assert registry["overview"] is notes
    assert "WARNING: duplicate link target" in capsys.readouterr().err
    assert registry["notes/overview"] is notes
    assert registry["projects/overview"] is projects


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
