"""Sample an ordered list of colors along a colorbar strip.

The output is always ordered min -> max so downstream code (ticks, SVG)
can assume a single convention. FE software conventionally puts the max
at the top (vertical bars) and at the right (horizontal bars); a ``flip``
flag XORs that default for the rare bar that runs the other way.
"""

import numpy as np
from PIL import Image


def sample_gradient(
    img: Image.Image,
    bbox: tuple[int, int, int, int],
    n_samples: int = 64,
    orientation: str = "vertical",
    flip: bool = False,
) -> list[tuple[int, int, int]]:
    """Return n_samples (R, G, B) tuples ordered from the min end to the max end.

    The short axis is collapsed with a *median* (not mean) so stray tick
    marks, label pixels or border lines intruding into the strip are
    rejected as outliers rather than smeared into the gradient.
    """
    left, top, right, bottom = (int(round(v)) for v in bbox[:4])
    crop = np.asarray(img.crop((left, top, right, bottom))).astype(np.float32)

    if crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
        return [(0, 0, 0)] * n_samples

    if orientation == "vertical":
        # long axis = rows (top->bottom); collapse columns.
        line = np.median(crop, axis=1)  # shape (H, 3)
        top_is_max = True
    else:
        # long axis = columns (left->right); collapse rows.
        line = np.median(crop, axis=0)  # shape (W, 3)
        top_is_max = False  # for horizontal, "right is max"

    length = line.shape[0]
    src = np.linspace(0, length - 1, length)
    dst = np.linspace(0, length - 1, n_samples)
    resampled = np.stack(
        [np.interp(dst, src, line[:, c]) for c in range(3)], axis=1
    )  # shape (n_samples, 3), in pixel order

    # Convert pixel order to canonical min->max order.
    # Vertical pixel order is top->bottom; with top=max we must reverse to get min->max.
    # Horizontal pixel order is left->right; with right=max it is already min->max.
    max_at_start = top_is_max  # True only for vertical default
    if max_at_start ^ flip:
        resampled = resampled[::-1]

    return [tuple(int(round(v)) for v in row) for row in resampled]


def build_swatch_preview(
    colors: list[tuple[int, int, int]],
    orientation: str = "vertical",
    long: int = 256,
    thick: int = 40,
) -> Image.Image:
    """Render the sampled colors as a simple strip for a quick visual check.

    The strip is shown min -> max left-to-right (or bottom-to-top) to match
    the canonical color ordering.
    """
    n = len(colors)
    if n == 0:
        return Image.new("RGB", (long, thick), (255, 255, 255))

    row = np.zeros((1, long, 3), dtype=np.uint8)
    idx = np.linspace(0, n - 1, long).round().astype(int)
    arr = np.array(colors, dtype=np.uint8)
    row[0] = arr[idx]

    if orientation == "vertical":
        # bottom = min, top = max
        strip = np.repeat(row, thick, axis=0)  # (thick, long, 3)
        strip = np.transpose(strip, (1, 0, 2))[::-1]  # (long, thick, 3), flip so top=max
        return Image.fromarray(strip)
    strip = np.repeat(row, thick, axis=0)
    return Image.fromarray(strip)
