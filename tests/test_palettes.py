from quarto_graph.palettes import (
    D3_CATEGORY10,
    OKABE_ITO,
    VIRIDIS_CTRL,
    assign_bucket_colors,
    golden_angle_hsv,
    sample_viridis,
)


def test_okabe_ito_palette_known_values():
    assert OKABE_ITO[0] == "#e69f00"
    assert OKABE_ITO[1] == "#56b4e9"
    assert len(OKABE_ITO) == 7


def test_d3_category10_known_values():
    assert D3_CATEGORY10[0] == "#1f77b4"
    assert D3_CATEGORY10[5] == "#8c564b"
    assert len(D3_CATEGORY10) == 10


def test_viridis_control_points_endpoints():
    assert VIRIDIS_CTRL[0] == (0.0, "#440154")
    assert VIRIDIS_CTRL[-1] == (1.0, "#fde725")


def test_sample_viridis_single_and_spread():
    assert sample_viridis(1) == ["#440154"]
    colors = sample_viridis(5)
    assert len(colors) == 5
    assert len(set(colors)) == 5
    assert colors[0] == "#440154"
    assert colors[-1] == "#fde725"


def test_golden_angle_generates_distinct_deterministic_colors():
    a = golden_angle_hsv(10)
    b = golden_angle_hsv(10)
    assert a == b
    assert len(set(a)) == 10


def test_assign_bucket_colors_uses_preset_for_small_n():
    colors = assign_bucket_colors(["a", "b", "c"], "okabe-ito")
    assert list(colors.values()) == ["#e69f00", "#56b4e9", "#009e73"]


def test_assign_bucket_colors_golden_angle_beyond_preset():
    buckets = ["f%02d" % i for i in range(15)]
    colors = assign_bucket_colors(buckets, "okabe-ito")
    assert len(set(colors.values())) == 15
    # First seven stay Okabe-Ito; the extra eight are auto-generated.
    assert colors["f00"] == "#e69f00"
    assert colors["f07"] != colors["f00"]


def test_assign_bucket_colors_viridis_samples_count():
    colors = assign_bucket_colors([0, 1, 2, 3], "viridis")
    assert len(colors) == 4
    assert len(set(colors.values())) == 4


def test_assign_bucket_colors_empty():
    assert assign_bucket_colors([], "okabe-ito") == {}
