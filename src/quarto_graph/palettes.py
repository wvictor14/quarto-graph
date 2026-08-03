"""Color palettes and bucket-to-color assignment.

No external deps. Pure Python. Palettes used by postrender to bake
per-scheme per-node hex into graph.json. JS reads only the baked hex.
"""

import math


OKABE_ITO = [
    "#e69f00",
    "#56b4e9",
    "#009e73",
    "#f0e442",
    "#0072b2",
    "#d55e00",
    "#cc79a7",
]

D3_CATEGORY10 = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

VIRIDIS_CTRL = [
    (0.0, "#440154"),
    (0.1, "#481567"),
    (0.2, "#4a2a7a"),
    (0.3, "#48408c"),
    (0.4, "#3e549b"),
    (0.5, "#2e6f9c"),
    (0.6, "#22879c"),
    (0.7, "#219f94"),
    (0.8, "#35b779"),
    (0.9, "#6ece58"),
    (1.0, "#fde725"),
]


DEFAULT_COLOR = "#9aa0a6"
ROOT_BUCKET = "(root)"


def _hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def _interp_rgb(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sample_viridis(n):
    """Sample n evenly spaced colors from viridis control points."""
    if n <= 1:
        return [VIRIDIS_CTRL[0][1]]
    colors = []
    for i in range(n):
        t = i / (n - 1)
        lo_idx = 0
        while lo_idx < len(VIRIDIS_CTRL) - 1 and VIRIDIS_CTRL[lo_idx + 1][0] <= t:
            lo_idx += 1
        if lo_idx == len(VIRIDIS_CTRL) - 1:
            colors.append(VIRIDIS_CTRL[-1][1])
        else:
            lo_t, lo_hex = VIRIDIS_CTRL[lo_idx]
            hi_t, hi_hex = VIRIDIS_CTRL[lo_idx + 1]
            seg_t = (t - lo_t) / (hi_t - lo_t)
            lo_rgb = _hex_to_rgb(lo_hex)
            hi_rgb = _hex_to_rgb(hi_hex)
            colors.append(_rgb_to_hex(_interp_rgb(lo_rgb, hi_rgb, seg_t)))
    return colors


def golden_angle_hsv(n, s=0.75, l=0.52):
    """Generate n colors via golden-angle hue spread. Returns hex list."""
    phi = (math.sqrt(5) - 1) / 2
    colors = []
    for i in range(n):
        h = ((i * phi) % 1.0) * 360.0
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60.0) % 2 - 1))
        m = l - c / 2
        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        rgb = tuple(int((v + m) * 255) for v in (r, g, b))
        colors.append(_rgb_to_hex(rgb))
    return colors


def _preset_for(palette_name):
    """Return preset list for qualitative palette name, or None."""
    if palette_name == "okabe-ito":
        return OKABE_ITO
    if palette_name == "d3-category10":
        return D3_CATEGORY10
    return None


def assign_bucket_colors(buckets, palette_name):
    """
    Assign a color to each bucket.

    buckets: iterable of bucket names (strings or ints), sorted externally.
    palette_name: "okabe-ito" | "d3-category10" | "viridis"

    Returns dict bucket -> hex.
    For qualitative palettes (okabe-ito, d3-category10): use preset up to
    its length, then golden-angle autogen for remaining.
    For viridis: interpolate n colors across 0..1.
    """
    buckets = list(buckets)
    n = len(buckets)
    if n == 0:
        return {}

    preset = _preset_for(palette_name)
    if preset is not None:
        if n <= len(preset):
            colors = preset[:n]
        else:
            extra = n - len(preset)
            colors = preset + golden_angle_hsv(extra)
    else:
        colors = sample_viridis(n)

    return {buckets[i]: colors[i] for i in range(n)}