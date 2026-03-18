"""
utils/scr_generator.py
AutoCAD SCR (script) file generator for SurveyCAD.

Builds a plain-text SCR file that AutoCAD can execute via its ``SCRIPT``
command.  The file uses Windows CRLF line endings and is written in binary
mode to avoid Python's universal-newline translation on Windows.  All
geometry helpers (``clean_code``, ``compute_placements``, ``label_positions``,
``DIR_VECTORS``) are imported from :mod:`utils.geometry` to eliminate
duplication with :mod:`utils.dxf_generator`.
"""

import os
import logging
from utils.geometry import clean_code, DIR_VECTORS, compute_placements, label_positions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coord(easting: float, northing: float) -> str:
    """Format coordinate string for AutoCAD commands."""
    return f"{easting:.4f},{northing:.4f}"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_scr(
    rows: list[dict],
    output_path: str,
    text_height: float = 1.0,
    offset: bool = True,
    polyline_codes: list[str] | None = None,
) -> None:
    """
    Generate an AutoCAD SCR script file from parsed survey rows.

    Parameters
    ----------
    rows : list[dict]
        Parsed survey data.  Each dict must contain ``easting``,
        ``northing``, and ``sr_no``; optionally ``elevation`` and
        ``description``.
    output_path : str
        Destination file path (will be created / overwritten).
    text_height : float
        AutoCAD text height for all labels.
    offset : bool
        Enable the anti-overlap label offset algorithm.
    polyline_codes : list[str] | None
        Description codes for which polylines should be drawn.
    """
    if polyline_codes is None:
        polyline_codes = []

    placements = compute_placements(rows, text_height, offset)
    lines: list[str] = []

    # 1. Layer Setup (NO COMMENTS AT TOP)
    # _-LAYER ensures command line version in any localized AutoCAD
    lines.append("_-LAYER")
    lines.append("N")
    lines.append("POINT,POINT_NUMBER,ELEVATION,DESCRIPTION")
    lines.append("C")
    lines.append("7")
    lines.append("POINT")
    lines.append("C")
    lines.append("2")
    lines.append("POINT_NUMBER")
    lines.append("C")
    lines.append("4")
    lines.append("ELEVATION")
    lines.append("C")
    lines.append("1")
    lines.append("DESCRIPTION")
    lines.append("")  # End layer command
    lines.append("PDMODE")
    lines.append("35")

    # 2. Draw Points
    lines.append("_-LAYER")
    lines.append("S")
    lines.append("POINT")
    lines.append("")
    for row in rows:
        lines.append("POINT")
        lines.append(_coord(float(row["easting"]), float(row["northing"])))

    # 3. Draw Sr_No Text
    lines.append("_-LAYER")
    lines.append("S")
    lines.append("POINT_NUMBER")
    lines.append("")
    for i, row in enumerate(rows):
        sr_no = str(row.get("sr_no", "")).strip()
        e, n = float(row["easting"]), float(row["northing"])
        d, m = placements[i]

        pos_sr, pos_desc, pos_elev = label_positions(e, n, text_height, d, m, offset)

        lines.append("-TEXT")
        lines.append(_coord(pos_sr[0], pos_sr[1]))
        lines.append(f"{text_height:.4f}")
        lines.append("0")  # Rotation
        lines.append(sr_no)

    # 4. Draw Description Text
    lines.append("_-LAYER")
    lines.append("S")
    lines.append("DESCRIPTION")
    lines.append("")
    for i, row in enumerate(rows):
        desc = row.get("description")
        if not desc or not str(desc).strip():
            continue
        e, n = float(row["easting"]), float(row["northing"])
        d, m = placements[i]

        pos_sr, pos_desc, pos_elev = label_positions(e, n, text_height, d, m, offset)

        lines.append("-TEXT")
        lines.append(_coord(pos_desc[0], pos_desc[1]))
        lines.append(f"{text_height:.4f}")
        lines.append("0")
        lines.append(str(desc).strip())

    # 5. Draw Elevation Text
    lines.append("_-LAYER")
    lines.append("S")
    lines.append("ELEVATION")
    lines.append("")
    for i, row in enumerate(rows):
        elev = row.get("elevation")
        if elev is None:
            continue
        e, n = float(row["easting"]), float(row["northing"])
        d, m = placements[i]

        pos_sr, pos_desc, pos_elev = label_positions(e, n, text_height, d, m, offset)

        lines.append("-TEXT")
        lines.append(_coord(pos_elev[0], pos_elev[1]))
        lines.append(f"{text_height:.4f}")
        lines.append("0")
        lines.append(f"{float(elev):.3f}")

    # 6. Draw Polylines
    for code in polyline_codes:
        code_str = str(code).strip()
        matched = [r for r in rows if str(r.get("description", "")).strip() == code_str]
        if len(matched) < 2:
            continue

        layer_name = f"PLINE_{clean_code(code_str)}"
        lines.append("_-LAYER")
        lines.append("N")
        lines.append(layer_name)
        lines.append("C")
        lines.append("3")  # Green
        lines.append(layer_name)
        lines.append("S")
        lines.append(layer_name)
        lines.append("")

        lines.append("PLINE")
        for r in matched:
            lines.append(_coord(float(r["easting"]), float(r["northing"])))
        lines.append("")  # End polyline

    # 7. Zoom Extents
    lines.append("ZOOM")
    lines.append("E")
    lines.append("")

    # 8. Write file with explicit CRLF (\r\n). ASCII encoding avoids any BOM.
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    content = "\r\n".join(lines) + "\r\n"

    # Important: open in binary mode so Python doesn't translate \r\n to \r\r\n on Windows
    with open(output_path, "wb") as f:
        f.write(content.encode("ascii", "replace"))

    logger.info("SCR file written correctly for AutoCAD Windows: %s", output_path)
