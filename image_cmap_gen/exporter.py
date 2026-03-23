import io
import pickle

import matplotlib.colors


def to_py_snippet(
    colors: list[tuple[int, int, int]],
    name: str,
    cmap_type: str = "linear",
) -> str:
    """Generate a self-contained Python snippet that recreates the colormap.

    Args:
        colors: List of (R, G, B) tuples in [0, 255].
        name: Colormap name.
        cmap_type: "linear" or "listed".

    Returns:
        A string of Python source code.
    """
    normalized = [(r / 255, g / 255, b / 255) for r, g, b in colors]
    color_repr = repr(normalized)

    if cmap_type == "listed":
        snippet = (
            "from matplotlib.colors import ListedColormap\n\n"
            f"_colors = {color_repr}\n"
            f'{name} = ListedColormap(_colors, name="{name}")\n\n'
            "# Usage:\n"
            "# import matplotlib.pyplot as plt\n"
            f'# plt.imshow(data, cmap={name})\n'
        )
    else:
        snippet = (
            "from matplotlib.colors import LinearSegmentedColormap\n\n"
            f"_colors = {color_repr}\n"
            f'{name} = LinearSegmentedColormap.from_list("{name}", _colors)\n\n'
            "# Usage:\n"
            "# import matplotlib.pyplot as plt\n"
            f'# plt.imshow(data, cmap={name})\n'
        )
    return snippet


def to_pickle(cmap: matplotlib.colors.Colormap) -> bytes:
    """Serialize a matplotlib Colormap to pickle bytes.

    Args:
        cmap: A matplotlib Colormap instance.

    Returns:
        Pickled bytes suitable for st.download_button.
    """
    buf = io.BytesIO()
    pickle.dump(cmap, buf)
    return buf.getvalue()
