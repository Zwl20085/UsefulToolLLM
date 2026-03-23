import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.figure import Figure
from PIL import Image


def _normalize(colors: list[tuple[int, int, int]]) -> list[tuple[float, float, float]]:
    return [(r / 255, g / 255, b / 255) for r, g, b in colors]


def build_cmap(
    colors: list[tuple[int, int, int]],
    name: str = "custom_cmap",
    cmap_type: str = "linear",
) -> matplotlib.colors.Colormap:
    """Build a matplotlib Colormap from a list of RGB colors.

    Args:
        colors: List of (R, G, B) tuples in [0, 255].
        name: Name to register the colormap under.
        cmap_type: "linear" (LinearSegmentedColormap) or "listed" (ListedColormap).

    Returns:
        A matplotlib Colormap instance.
    """
    normalized = _normalize(colors)
    if cmap_type == "listed":
        return ListedColormap(normalized, name=name)
    return LinearSegmentedColormap.from_list(name, normalized)


def preview_cmap(cmap: matplotlib.colors.Colormap) -> Figure:
    """Return a 2-panel matplotlib Figure: gradient bar + sample heatmap.

    Args:
        cmap: A matplotlib Colormap.

    Returns:
        matplotlib Figure.
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 2))

    # Panel 1: gradient bar
    gradient = np.linspace(0, 1, 256).reshape(1, -1)
    axes[0].imshow(gradient, aspect="auto", cmap=cmap)
    axes[0].set_title("Gradient")
    axes[0].axis("off")

    # Panel 2: sample heatmap (sine-wave pattern)
    x = np.linspace(0, 2 * np.pi, 64)
    y = np.linspace(0, 2 * np.pi, 64)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(X) * np.cos(Y)
    axes[1].imshow(Z, cmap=cmap, aspect="auto")
    axes[1].set_title("Sample Heatmap")
    axes[1].axis("off")

    fig.tight_layout()
    return fig


def build_swatch_image(
    colors: list[tuple[int, int, int]],
    swatch_w: int = 80,
    swatch_h: int = 60,
) -> Image.Image:
    """Build a horizontal color swatch strip as a PIL Image.

    Args:
        colors: List of (R, G, B) tuples.
        swatch_w: Width of each swatch in pixels.
        swatch_h: Height of the strip in pixels.

    Returns:
        PIL Image showing each color as a rectangle.
    """
    n = len(colors)
    strip = Image.new("RGB", (n * swatch_w, swatch_h))
    for i, color in enumerate(colors):
        block = Image.new("RGB", (swatch_w, swatch_h), color)
        strip.paste(block, (i * swatch_w, 0))
    return strip
