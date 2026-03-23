import colorsys

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from utils import resize_for_processing


def extract_colors(
    image: Image.Image,
    n_colors: int = 8,
    method: str = "kmeans",
) -> list[tuple[int, int, int]]:
    """Extract dominant colors from an image.

    Args:
        image: PIL RGB image.
        n_colors: Number of colors to extract.
        method: "kmeans" (default) or "quantize".

    Returns:
        List of (R, G, B) tuples in [0, 255].
    """
    small = resize_for_processing(image, max_side=200)

    if method == "quantize":
        quantized = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()  # flat list [R,G,B, R,G,B, ...]
        colors = [
            (palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2])
            for i in range(n_colors)
        ]
        return colors

    # KMeans (default)
    pixels = np.array(small).reshape(-1, 3).astype(float)
    km = KMeans(n_clusters=n_colors, n_init="auto", random_state=42)
    km.fit(pixels)
    centers = km.cluster_centers_.astype(int)
    return [(int(r), int(g), int(b)) for r, g, b in centers]


def sort_colors(
    colors: list[tuple[int, int, int]],
    strategy: str = "luminance",
) -> list[tuple[int, int, int]]:
    """Sort a list of (R, G, B) colors by the given strategy.

    Args:
        colors: List of (R, G, B) tuples.
        strategy: "luminance" (default), "hue", or "none".

    Returns:
        Sorted list of (R, G, B) tuples.
    """
    if strategy == "none":
        return list(colors)

    if strategy == "hue":
        def key(c):
            h, _, _ = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
            return h
        return sorted(colors, key=key)

    # Default: luminance
    def luminance(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    return sorted(colors, key=luminance)
