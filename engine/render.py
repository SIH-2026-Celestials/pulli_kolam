"""Deterministic rendering: graph/trace -> dot-lattice + stroke geometry
-> image (SVG string or PNG file). Pure geometry, no ML, no randomness --
the same structural input plus the same layout config always produces
the same output (byte-identical for SVG; pixel-identical for PNG, since
PIL's drawing primitives and its built-in bitmap font are used, not a
system-dependent TrueType font).

WHAT THIS DOES NOT CLAIM: for a `GeneratedKolam` candidate, the drawn
stroke is a sequence of STRAIGHT LINE SEGMENTS between consecutive dots
in `dot_trace` -- not a reconstruction of the curved, loop-around stroke
geometry real Kolam drawings use (see docs/GENERATION.md "Trace
reconstruction" for why that reconstruction is out of scope: the graph
topology alone does not determine which side of a skipped dot a curve
arcs around). For a `KolamPattern` loaded from a source CSV, the ACTUAL
recorded stroke geometry (`pattern.trace_points`, dense float
coordinates including loop-arounds) is rendered instead -- this is real
drawn geometry, not an approximation.

An invalid `GeneratedKolam` (is_valid == False) is never drawn with a
fabricated stroke -- generate_kolam already leaves `dot_trace` as None
for an invalid candidate (see engine/generation.py), so rendering it
naturally produces a dots-only diagram. This module additionally labels
it explicitly ("INVALID") rather than silently producing a picture that
merely happens to have no lines, so a viewer cannot mistake "no stroke
was reconstructible" for "this pattern has no strokes by design".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.generated_kolam import GeneratedKolam
    from engine.kolam_pattern import KolamPattern

Point = tuple[int, int]
TracePoint = tuple[float, float]

DEFAULT_SCALE = 40.0
DEFAULT_MARGIN = 40.0
DEFAULT_DOT_RADIUS_FRAC = 0.18  # fraction of `scale`


def _layout(dot_points, scale: float, margin: float):
    """Shared pixel-space layout: integer/float lattice coordinates ->
    (width, height, to_px). `to_px` is used identically by both the SVG
    and PNG renderers so the two always agree on where things are drawn."""
    xs = [p[0] for p in dot_points]
    ys = [p[1] for p in dot_points]
    min_x, max_x = (min(xs), max(xs)) if xs else (0, 0)
    min_y, max_y = (min(ys), max(ys)) if ys else (0, 0)
    width = (max_x - min_x) * scale + 2 * margin
    height = (max_y - min_y) * scale + 2 * margin

    def to_px(p):
        x, y = p
        return (margin + (x - min_x) * scale, margin + (y - min_y) * scale)

    return max(width, 2 * margin), max(height, 2 * margin), to_px


def render_trace_svg(
    dot_points,
    trace: "list[tuple[float, float]] | None",
    scale: float = DEFAULT_SCALE,
    margin: float = DEFAULT_MARGIN,
    dot_radius_frac: float = DEFAULT_DOT_RADIUS_FRAC,
    label: str | None = None,
) -> str:
    """The one shared SVG primitive: a set of dots plus an optional
    stroke trace (any sequence of (x, y) points in the SAME coordinate
    space as `dot_points` -- lattice-integer or dense float, both work
    since this function only ever scales/translates, never assumes
    integer input). `trace=None` renders dots only.
    """
    width, height, to_px = _layout(dot_points, scale, margin)
    r = scale * dot_radius_frac

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="0 0 {width:.2f} {height:.2f}">',
        f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="#F7F4ED"/>',
    ]

    if trace and len(trace) >= 2:
        pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in (to_px(p) for p in trace))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#252321" stroke-width="2"/>')

    for p in sorted(dot_points):
        cx, cy = to_px(p)
        parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="#8A3324"/>')

    if label:
        parts.append(f'<text x="{margin:.2f}" y="{(margin * 0.6):.2f}" font-size="16" fill="#8A3324">{label}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def render_trace_png(
    dot_points,
    trace: "list[tuple[float, float]] | None",
    path: str,
    scale: float = DEFAULT_SCALE,
    margin: float = DEFAULT_MARGIN,
    dot_radius_frac: float = DEFAULT_DOT_RADIUS_FRAC,
    label: str | None = None,
):
    """PNG counterpart to render_trace_svg, same layout math (`_layout`),
    so SVG and PNG output always agree on dot/stroke placement. Uses
    PIL's built-in bitmap font for `label` (not a system TrueType font)
    so output is reproducible across machines, not just across calls on
    the same machine."""
    from PIL import Image, ImageDraw

    width, height, to_px = _layout(dot_points, scale, margin)
    r = scale * dot_radius_frac

    img = Image.new("RGB", (int(round(width)), int(round(height))), color=(247, 244, 237))
    draw = ImageDraw.Draw(img)

    if trace and len(trace) >= 2:
        px_pts = [to_px(p) for p in trace]
        draw.line(px_pts, fill=(37, 35, 33), width=2, joint="curve")

    for p in sorted(dot_points):
        cx, cy = to_px(p)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(138, 51, 36))

    if label:
        draw.text((margin, margin * 0.3), label, fill=(138, 51, 36))

    img.save(path, format="PNG")
    return path


def render_generated_kolam_svg(candidate: "GeneratedKolam", **layout_kwargs) -> str:
    """`GeneratedKolam` -> SVG. The stroke, if any, is `dot_trace`
    rendered as straight segments between consecutive dots (see module
    docstring for what this does and does not claim). An invalid
    candidate is rendered dots-only and explicitly labeled 'INVALID' --
    never a silently-blank success-looking image."""
    label = None if candidate.is_valid else "INVALID -- no single-stroke trace reconstructed"
    return render_trace_svg(candidate.dot_points, candidate.dot_trace, label=label, **layout_kwargs)


def render_generated_kolam_png(candidate: "GeneratedKolam", path: str, **layout_kwargs) -> str:
    label = None if candidate.is_valid else "INVALID"
    return render_trace_png(candidate.dot_points, candidate.dot_trace, path, label=label, **layout_kwargs)


def render_kolam_pattern_svg(pattern: "KolamPattern", **layout_kwargs) -> str:
    """`KolamPattern` -> SVG, using the pattern's ACTUAL recorded stroke
    geometry (`pattern.trace_points`, dense float coordinates including
    loop-arounds) -- this is real drawn geometry from the source data,
    not an approximation like the generated-candidate renderer above."""
    return render_trace_svg(pattern.dot_points, list(pattern.trace_points), **layout_kwargs)


def render_kolam_pattern_png(pattern: "KolamPattern", path: str, **layout_kwargs) -> str:
    return render_trace_png(pattern.dot_points, list(pattern.trace_points), path, **layout_kwargs)
