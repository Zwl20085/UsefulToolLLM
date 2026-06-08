"""Build a clean SVG colorbar by hand (no external SVG dependency).

A matching PIL raster is also produced for the in-app preview so the UI
never depends on a browser-side SVG renderer.

Conventions (shared with sampler/ticks):
  * ``colors`` is ordered min -> max.
  * tick ``fraction`` runs 0..1 from the min end.
  * vertical bars put min at the bottom; horizontal bars put min at the left.
"""

from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_PAD = 12
_TICK_LEN = 6
_GAP = 4


def _label_title(title: str, units: str) -> str:
    title, units = title.strip(), units.strip()
    if title and units:
        return f"{title} [{units}]"
    if units:
        return f"[{units}]"
    return title


def _est_text_w(text: str, font_size: int) -> float:
    return 0.6 * font_size * len(text)


def _rgb(c) -> str:
    return f"rgb({int(c[0])},{int(c[1])},{int(c[2])})"


def build_svg(
    colors: list[tuple[int, int, int]],
    ticks: list[tuple[float, str]],
    orientation: str = "vertical",
    mode: str = "gradient",
    title: str = "",
    units: str = "",
    bar_length: int = 320,
    bar_thickness: int = 30,
    border: bool = True,
    font_size: int = 14,
) -> str:
    """Return an SVG document string for the colorbar."""
    title_text = _label_title(title, units)
    title_h = int(font_size * 1.8) if title_text else 0
    max_label_w = max((_est_text_w(lbl, font_size) for _, lbl in ticks), default=0.0)

    parts: list[str] = []
    defs: list[str] = []
    body: list[str] = []

    title_w = _est_text_w(title_text, font_size) if title_text else 0.0

    if orientation == "vertical":
        bar_y = _PAD + title_h
        # Natural content width (bar + ticks + labels); widen if the title is longer.
        content_w = _PAD + bar_thickness + _TICK_LEN + _GAP + max_label_w + _PAD
        canvas_w = int(round(max(content_w, title_w + 2 * _PAD)))
        dx = (canvas_w - content_w) / 2  # center content when the title widened the canvas
        bar_x = _PAD + dx
        label_x = bar_x + bar_thickness + _TICK_LEN + _GAP
        canvas_h = int(bar_y + bar_length + _PAD)

        # Gradient: offset 0% (min) at bottom -> y1=1, y2=0.
        if mode == "gradient":
            stops = _gradient_stops(colors)
            defs.append(
                f'<linearGradient id="cbgrad" x1="0" y1="1" x2="0" y2="0">{stops}</linearGradient>'
            )
            body.append(
                f'<rect x="{bar_x}" y="{bar_y}" width="{bar_thickness}" '
                f'height="{bar_length}" fill="url(#cbgrad)"/>'
            )
        else:
            n = len(colors)
            seg = bar_length / n
            for i, c in enumerate(colors):
                # color[0]=min at bottom; rect from bottom upward.
                y = bar_y + bar_length - (i + 1) * seg
                body.append(
                    f'<rect x="{bar_x}" y="{y:.2f}" width="{bar_thickness}" '
                    f'height="{seg:.2f}" fill="{_rgb(c)}"/>'
                )

        if border:
            body.append(
                f'<rect x="{bar_x}" y="{bar_y}" width="{bar_thickness}" '
                f'height="{bar_length}" fill="none" stroke="black" stroke-width="1"/>'
            )

        for frac, label in ticks:
            y = bar_y + bar_length * (1 - frac)
            x0 = bar_x + bar_thickness
            body.append(
                f'<line x1="{x0}" y1="{y:.2f}" x2="{x0 + _TICK_LEN}" y2="{y:.2f}" '
                f'stroke="black" stroke-width="1"/>'
            )
            body.append(
                f'<text x="{label_x}" y="{y:.2f}" font-family="sans-serif" '
                f'font-size="{font_size}" text-anchor="start" '
                f'dominant-baseline="middle">{escape(label)}</text>'
            )

        if title_text:
            cx = canvas_w / 2
            body.append(
                f'<text x="{cx:.2f}" y="{_PAD + font_size}" font-family="sans-serif" '
                f'font-size="{font_size}" text-anchor="middle">{escape(title_text)}</text>'
            )

    else:  # horizontal
        bar_y = _PAD + title_h
        side_margin = max(_PAD, max_label_w / 2)
        content_w = bar_length + 2 * side_margin
        canvas_w = int(round(max(content_w, title_w + 2 * _PAD)))
        bar_x = (canvas_w - bar_length) / 2  # center bar; covers both label and title overhang
        canvas_h = int(bar_y + bar_thickness + _TICK_LEN + _GAP + font_size + _PAD)

        if mode == "gradient":
            stops = _gradient_stops(colors)
            defs.append(
                f'<linearGradient id="cbgrad" x1="0" y1="0" x2="1" y2="0">{stops}</linearGradient>'
            )
            body.append(
                f'<rect x="{bar_x}" y="{bar_y}" width="{bar_length}" '
                f'height="{bar_thickness}" fill="url(#cbgrad)"/>'
            )
        else:
            n = len(colors)
            seg = bar_length / n
            for i, c in enumerate(colors):
                x = bar_x + i * seg  # color[0]=min at left
                body.append(
                    f'<rect x="{x:.2f}" y="{bar_y}" width="{seg:.2f}" '
                    f'height="{bar_thickness}" fill="{_rgb(c)}"/>'
                )

        if border:
            body.append(
                f'<rect x="{bar_x}" y="{bar_y}" width="{bar_length}" '
                f'height="{bar_thickness}" fill="none" stroke="black" stroke-width="1"/>'
            )

        label_y = bar_y + bar_thickness + _TICK_LEN + _GAP + font_size * 0.8
        for frac, label in ticks:
            x = bar_x + bar_length * frac
            y0 = bar_y + bar_thickness
            body.append(
                f'<line x1="{x:.2f}" y1="{y0}" x2="{x:.2f}" y2="{y0 + _TICK_LEN}" '
                f'stroke="black" stroke-width="1"/>'
            )
            body.append(
                f'<text x="{x:.2f}" y="{label_y:.2f}" font-family="sans-serif" '
                f'font-size="{font_size}" text-anchor="middle">{escape(label)}</text>'
            )

        if title_text:
            cx = canvas_w / 2
            body.append(
                f'<text x="{cx:.2f}" y="{_PAD + font_size}" font-family="sans-serif" '
                f'font-size="{font_size}" text-anchor="middle">{escape(title_text)}</text>'
            )

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" '
        f'height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">'
    )
    if defs:
        parts.append("<defs>" + "".join(defs) + "</defs>")
    parts.append("".join(body))
    parts.append("</svg>")
    return "\n".join(parts)


def _gradient_stops(colors: list[tuple[int, int, int]]) -> str:
    n = len(colors)
    if n == 0:
        return ""
    if n == 1:
        return f'<stop offset="0%" stop-color="{_rgb(colors[0])}"/>'
    out = []
    for i, c in enumerate(colors):
        offset = 100.0 * i / (n - 1)
        out.append(f'<stop offset="{offset:.2f}%" stop-color="{_rgb(c)}"/>')
    return "".join(out)


# ── Raster preview (visually matches the SVG) ─────────────────────────────────


def _load_font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_preview_png(
    colors: list[tuple[int, int, int]],
    ticks: list[tuple[float, str]],
    orientation: str = "vertical",
    mode: str = "gradient",
    title: str = "",
    units: str = "",
    bar_length: int = 320,
    bar_thickness: int = 30,
    border: bool = True,
    font_size: int = 14,
) -> Image.Image:
    """Render a raster colorbar matching build_svg (for st.image previews)."""
    title_text = _label_title(title, units)
    title_h = int(font_size * 1.8) if title_text else 0
    font = _load_font(font_size)
    n = max(1, len(colors))
    arr = np.array(colors if colors else [(0, 0, 0)], dtype=np.uint8)

    def color_strip(length: int) -> np.ndarray:
        if mode == "gradient":
            pos = np.linspace(0, n - 1, length)
            lo = np.floor(pos).astype(int)
            hi = np.minimum(lo + 1, n - 1)
            t = (pos - lo)[:, None]
            return (arr[lo] * (1 - t) + arr[hi] * t).astype(np.uint8)
        idx = np.minimum((np.arange(length) * n // length), n - 1)
        return arr[idx]

    title_w = font.getlength(title_text) if title_text else 0.0

    if orientation == "vertical":
        bar_y = _PAD + title_h
        max_label_w = max((font.getlength(lbl) for _, lbl in ticks), default=0)
        content_w = _PAD + bar_thickness + _TICK_LEN + _GAP + max_label_w + _PAD
        canvas_w = int(round(max(content_w, title_w + 2 * _PAD)))
        dx = (canvas_w - content_w) / 2
        bar_x = _PAD + dx
        label_x = bar_x + bar_thickness + _TICK_LEN + _GAP
        canvas_h = int(bar_y + bar_length + _PAD)
        img = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

        strip = color_strip(bar_length)[::-1]  # row 0 = top = max
        block = np.repeat(strip[:, None, :], bar_thickness, axis=1)
        img.paste(Image.fromarray(block), (int(round(bar_x)), bar_y))
        draw = ImageDraw.Draw(img)
        if border:
            draw.rectangle(
                [bar_x, bar_y, bar_x + bar_thickness, bar_y + bar_length], outline=(0, 0, 0)
            )
        for frac, label in ticks:
            y = bar_y + bar_length * (1 - frac)
            x0 = bar_x + bar_thickness
            draw.line([(x0, y), (x0 + _TICK_LEN, y)], fill=(0, 0, 0))
            draw.text((label_x, y), label, fill=(0, 0, 0), font=font, anchor="lm")
        if title_text:
            draw.text(
                (canvas_w / 2, _PAD), title_text, fill=(0, 0, 0), font=font, anchor="ma"
            )
        return img

    # horizontal
    max_label_w = max((font.getlength(lbl) for _, lbl in ticks), default=0)
    side_margin = max(_PAD, max_label_w / 2)
    bar_y = _PAD + title_h
    content_w = bar_length + 2 * side_margin
    canvas_w = int(round(max(content_w, title_w + 2 * _PAD)))
    bar_x = (canvas_w - bar_length) / 2
    canvas_h = int(bar_y + bar_thickness + _TICK_LEN + _GAP + font_size + _PAD)
    img = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    strip = color_strip(bar_length)  # index 0 = left = min
    block = np.repeat(strip[None, :, :], bar_thickness, axis=0)
    img.paste(Image.fromarray(block), (int(round(bar_x)), bar_y))
    draw = ImageDraw.Draw(img)
    if border:
        draw.rectangle(
            [bar_x, bar_y, bar_x + bar_length, bar_y + bar_thickness], outline=(0, 0, 0)
        )
    label_y = bar_y + bar_thickness + _TICK_LEN + _GAP
    for frac, label in ticks:
        x = bar_x + bar_length * frac
        y0 = bar_y + bar_thickness
        draw.line([(x, y0), (x, y0 + _TICK_LEN)], fill=(0, 0, 0))
        draw.text((x, label_y), label, fill=(0, 0, 0), font=font, anchor="ma")
    if title_text:
        draw.text(
            (canvas_w / 2, _PAD), title_text, fill=(0, 0, 0), font=font, anchor="ma"
        )
    return img
