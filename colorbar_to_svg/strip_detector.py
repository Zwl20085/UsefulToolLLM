"""Locate the colored gradient strip inside a colorbar screenshot.

The screenshot also contains a white/gray background and black numeric
labels. The strip is the one region that is genuinely *colorful*, so a
chroma metric (max channel - min channel) cleanly isolates it: white,
gray and black all have chroma ~0, while even a dark-but-saturated
viridis purple keeps a high chroma. This works where plain HSV
saturation would fail on dark colors.
"""

from collections import namedtuple

import numpy as np
from PIL import Image, ImageDraw

from utils import resize_for_processing

StripBBox = namedtuple(
    "StripBBox", "left top right bottom orientation confidence"
)

# Detection runs on a copy no larger than this on its long side.
_MAX_SIDE = 512


def chroma_map(arr: np.ndarray) -> np.ndarray:
    """Per-pixel chroma = max(R,G,B) - min(R,G,B), as float in [0, 255]."""
    a = arr.astype(np.float32)
    return a.max(axis=2) - a.min(axis=2)


def _contiguous_run(frac: np.ndarray, rel: float = 0.5):
    """Return (start, stop_exclusive) of the longest run above rel*peak."""
    peak = float(frac.max()) if frac.size else 0.0
    if peak <= 0:
        return 0, len(frac)
    above = frac >= rel * peak
    best_len, best_start = 0, 0
    i = 0
    n = len(above)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            if j - i > best_len:
                best_len, best_start = j - i, i
            i = j
        else:
            i += 1
    return best_start, best_start + best_len


def detect_strip(img: Image.Image, sat_threshold: float | None = None) -> StripBBox:
    """Auto-detect the colored strip's bounding box and orientation.

    Returns a StripBBox in full-resolution pixel coordinates. ``confidence``
    is the peak colored-fraction of the band (0..1); low values mean the UI
    should fall back to manual adjustment.
    """
    small = resize_for_processing(img, _MAX_SIDE)
    scale = img.size[0] / small.size[0]  # full / small (uniform aspect)
    arr = np.asarray(small)

    chroma = chroma_map(arr)
    thr = sat_threshold if sat_threshold is not None else max(25.0, 0.4 * float(chroma.max()))
    mask = chroma >= thr

    if not mask.any():
        # No colorful region found at all: return the whole image, low confidence.
        return StripBBox(0, 0, img.size[0], img.size[1], "vertical", 0.0)

    col_frac = mask.mean(axis=0)  # one value per column
    row_frac = mask.mean(axis=1)  # one value per row

    left, right = _contiguous_run(col_frac)
    top, bottom = _contiguous_run(row_frac)

    # Confidence = colored-pixel density inside the detected box. A clean strip
    # is almost entirely colored; a spurious box catches background and scores low.
    region = mask[top:bottom, left:right]
    confidence = float(region.mean()) if region.size else 0.0

    # Map back to full resolution.
    L = int(round(left * scale))
    R = int(round(right * scale))
    T = int(round(top * scale))
    B = int(round(bottom * scale))
    W, H = img.size
    L, R = max(0, L), min(W, R)
    T, B = max(0, T), min(H, B)

    orientation = "vertical" if (B - T) >= (R - L) else "horizontal"
    return StripBBox(L, T, R, B, orientation, confidence)


def inset_bbox(bbox, frac: float = 0.06) -> tuple[int, int, int, int]:
    """Shrink a bbox inward to drop the frame / anti-aliased border pixels.

    Accepts a StripBBox or a (left, top, right, bottom) tuple.
    """
    left, top, right, bottom = bbox[0], bbox[1], bbox[2], bbox[3]
    short = max(1, min(right - left, bottom - top))
    pad = max(1, round(frac * short))
    # Never collapse the box.
    if right - left > 2 * pad:
        left, right = left + pad, right - pad
    if bottom - top > 2 * pad:
        top, bottom = top + pad, bottom - pad
    return int(left), int(top), int(right), int(bottom)


def draw_bbox_overlay(img: Image.Image, bbox) -> Image.Image:
    """Return a copy of img with the bbox drawn on top (for live preview)."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    left, top, right, bottom = bbox[0], bbox[1], bbox[2], bbox[3]
    width = max(2, round(0.004 * max(img.size)))
    draw.rectangle([left, top, right - 1, bottom - 1], outline=(255, 0, 0), width=width)
    return out
