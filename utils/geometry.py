"""
utils/geometry.py
Shared geometry and positioning utilities for SurveyCAD generators.

Provides sanitisation for AutoCAD layer names, 8-direction unit vectors
for label placement, per-point overlap-avoidance computation, and
final label position calculation.  Both scr_generator and dxf_generator
import exclusively from this module so that the geometry logic is
defined in exactly one place.
"""

import math
import re


def clean_code(code: str) -> str:
    """
    Sanitize a survey description code for use as an AutoCAD layer name.

    Replace any character that is not alphanumeric or underscore with
    underscore and return the result in uppercase.

    Examples
    --------
    >>> clean_code('C IB')
    'C_IB'
    >>> clean_code('FND SIB')
    'FND_SIB'
    """
    return re.sub(r"[^\w]", "_", code).upper()


DIR_VECTORS: list[tuple[int, int]] = [
    (1, 0),    # E
    (1, 1),    # NE
    (0, 1),    # N
    (-1, 1),   # NW
    (-1, 0),   # W
    (-1, -1),  # SW
    (0, -1),   # S
    (1, -1),   # SE
]


def compute_placements(
    rows: list[dict],
    text_height: float,
    offset_enabled: bool,
) -> list[tuple[int, float]]:
    """
    Compute per-point label direction and multiplier to minimize text overlap.

    Parameters
    ----------
    rows : list[dict]
        Parsed survey rows, each containing at least ``easting`` and
        ``northing`` keys.
    text_height : float
        The text height used for label rendering.
    offset_enabled : bool
        When *False*, every point receives direction 0 and multiplier 1.0,
        effectively disabling the anti-overlap algorithm.

    Returns
    -------
    list[tuple[int, float]]
        A list parallel to *rows* of ``(direction_index, multiplier)`` pairs.

    Raises
    ------
    ValueError
        If ``len(rows)`` exceeds 5 000 to prevent runaway computation.
    """
    if not offset_enabled:
        return [(0, 1.0)] * len(rows)
    if not rows:
        return []
    if len(rows) > 5000:
        raise ValueError("Row count exceeds 5000 limit.")

    threshold: float = text_height * 15
    placements: list[tuple[int, float]] = []

    for i in range(len(rows)):
        ei: float = float(rows[i]["easting"])
        ni: float = float(rows[i]["northing"])
        used = set()

        for j in range(i):
            ej: float = float(rows[j]["easting"])
            nj: float = float(rows[j]["northing"])
            if math.hypot(ei - ej, ni - nj) < threshold:
                used.add(placements[j])

        placed: bool = False
        for mult in (1.0, 2.0, 3.0):
            for d in range(8):
                if (d, mult) not in used:
                    placements.append((d, mult))
                    placed = True
                    break
            if placed:
                break

        if not placed:
            placements.append((i % 8, 1.0 + (i % 3)))

    return placements


def label_positions(
    easting: float,
    northing: float,
    text_height: float,
    direction: int,
    multiplier: float,
    offset_enabled: bool,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """
    Return three ``(x, y)`` positions for the *sr_no*, *description*, and
    *elevation* labels of a single survey point.

    Parameters
    ----------
    easting, northing : float
        Point coordinates.
    text_height : float
        Height of the text style used for labelling.
    direction : int
        Index into :data:`DIR_VECTORS` (0–7).
    multiplier : float
        Offset multiplier (1.0, 2.0, 3.0, …).
    offset_enabled : bool
        When *False*, labels are placed directly at the point coordinates.

    Returns
    -------
    tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
        ``(sr_no_pos, description_pos, elevation_pos)``
    """
    gap: float = text_height * 2.0 * multiplier if offset_enabled else 0.0
    line_spacing: float = text_height * 2.0
    dx: int
    dy: int
    dx, dy = DIR_VECTORS[direction]

    base: tuple[float, float] = (easting + dx * gap, northing + dy * gap)
    sr_no_pos: tuple[float, float] = base
    desc_pos: tuple[float, float] = (base[0], base[1] - line_spacing)
    elev_pos: tuple[float, float] = (base[0], base[1] - line_spacing * 2)

    return sr_no_pos, desc_pos, elev_pos
