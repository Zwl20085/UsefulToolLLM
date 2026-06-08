"""Reduce a colorbar to a small set of evenly-spaced, nicely-formatted ticks.

FE software prints far too many tick values; here the user supplies only
``vmin``/``vmax``/scale and a desired count (4-8) and we generate evenly
spaced labels along the bar.
"""

import math

import numpy as np


def make_ticks(
    vmin: float, vmax: float, count: int, scale: str = "linear"
) -> list[tuple[float, float]]:
    """Return ``count`` (fraction_from_min, value) pairs.

    ``fraction_from_min`` runs 0..1 from the min end of the bar. For a log
    scale the positions are still evenly spaced because a log colorbar maps
    log-space linearly onto the bar length; ``vmin`` and ``vmax`` must be > 0.
    """
    count = int(max(2, count))
    fractions = np.linspace(0.0, 1.0, count)

    if scale == "log":
        if vmin <= 0 or vmax <= 0:
            raise ValueError("Log scale requires vmin > 0 and vmax > 0.")
        logs = np.linspace(math.log10(vmin), math.log10(vmax), count)
        values = np.power(10.0, logs)
    else:
        values = np.linspace(vmin, vmax, count)

    return list(zip(fractions.tolist(), values.tolist()))


def format_value(value: float, reference_values: list[float], sig: int = 4) -> str:
    """Format one value to ``sig`` significant figures.

    The scientific-vs-fixed choice is made once from the whole tick set's
    magnitude so all labels share a style; within fixed style each value keeps
    its own precision (so 62.5 stays "62.5" even when 250 is also present).
    """
    if value == 0:
        return "0"

    nonzero = [abs(v) for v in reference_values if v != 0]
    m = max(nonzero) if nonzero else abs(value)

    # Scientific notation for very large or very small magnitudes.
    if m >= 1e4 or m < 1e-3:
        return f"{value:.{max(1, sig - 1)}e}"

    # Fixed notation, per-value significant figures, trailing zeros stripped.
    decimals = max(0, sig - int(math.floor(math.log10(abs(value)))) - 1)
    s = f"{value:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def format_ticks(ticks: list[tuple[float, float]]) -> list[tuple[float, str]]:
    """Map (fraction, value) pairs to (fraction, label) pairs."""
    values = [v for _, v in ticks]
    return [(frac, format_value(v, values)) for frac, v in ticks]
