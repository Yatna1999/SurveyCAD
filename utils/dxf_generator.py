"""
utils/dxf_generator.py
DXF file generator for SurveyCAD Converter.

Creates a proper DXF drawing using the *ezdxf* library.  Survey points,
serial-number labels, description labels, elevation labels, and optional
polylines are placed on separate, colour-coded layers.  The same 8-direction
anti-overlap logic used by the SCR generator is applied here; the shared
helpers (``clean_code``, ``compute_placements``, ``label_positions``) are
imported from :mod:`utils.geometry`.
"""

import logging
import os
import ezdxf
from utils.geometry import clean_code, compute_placements, label_positions

logger = logging.getLogger(__name__)

UNITS_MAP: dict[str, int] = {"meters": 6, "millimeters": 4, "feet": 2}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_dxf(
    rows: list[dict],
    output_path: str,
    text_height: float = 1.0,
    offset: bool = True,
    polyline_codes: list[str] | None = None,
    units: str = "meters",
) -> None:
    """
    Generate an AutoCAD DXF file from parsed survey rows.

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
    units : str
        Drawing units — ``'meters'``, ``'millimeters'``, or ``'feet'``.
    """
    if polyline_codes is None:
        polyline_codes = []

    placements = compute_placements(rows, text_height, offset)

    doc = ezdxf.new("R2018")
    doc.units = UNITS_MAP.get(units, 6)
    msp = doc.modelspace()

    doc.layers.add("POINT",        color=7)
    doc.layers.add("POINT_NUMBER", color=2)
    doc.layers.add("ELEVATION",    color=4)
    doc.layers.add("DESCRIPTION",  color=1)

    for idx, row in enumerate(rows):
        sr_no: str = str(row.get("sr_no", "")).strip()
        northing: float = float(row["northing"])
        easting: float = float(row["easting"])
        elevation = row.get("elevation")
        description = row.get("description")
        if description is not None and not str(description).strip():
            description = None

        z: float = float(elevation) if elevation is not None else 0.0
        direction, mult = placements[idx]
        sr_pos, desc_pos, elev_pos = label_positions(
            easting, northing, text_height, direction, mult, offset
        )

        msp.add_point((easting, northing, z), dxfattribs={"layer": "POINT"})

        msp.add_text(sr_no, dxfattribs={
            "layer": "POINT_NUMBER", "height": text_height,
            "insert": (sr_pos[0], sr_pos[1], 0),
        })

        if description:
            msp.add_text(str(description), dxfattribs={
                "layer": "DESCRIPTION", "height": text_height,
                "insert": (desc_pos[0], desc_pos[1], 0),
            })

        if elevation is not None:
            try:
                elev_val: float = float(elevation)
                msp.add_text(f"{elev_val:.3f}", dxfattribs={
                    "layer": "ELEVATION", "height": text_height,
                    "insert": (elev_pos[0], elev_pos[1], 0),
                })
            except (ValueError, TypeError):
                pass

    for code in polyline_codes:
        pts: list[tuple[float, float]] = [
            (float(r["easting"]), float(r["northing"]))
            for r in rows
            if r.get("description") and str(r["description"]).strip() == str(code).strip()
        ]
        if len(pts) < 2:
            continue
        layer_name: str = f"PLINE_{clean_code(str(code))}"
        if doc.layers.get(layer_name) is None:
            doc.layers.add(layer_name, color=3)
        msp.add_lwpolyline(pts, dxfattribs={"layer": layer_name, "closed": False})

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.saveas(output_path)
    logger.info("DXF file written: %s", output_path)
