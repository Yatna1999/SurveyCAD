"""DXF generator for SurveyCAD (uses ezdxf)."""

import io, logging, ezdxf
from utils.geometry import clean_code, label_positions

logger = logging.getLogger(__name__)

UNITS_MAP = {"meters": 6, "millimeters": 4, "feet": 2}


def generate_dxf_doc(rows, text_height=1.0, offset=True,
                     polyline_codes=None, units="meters"):
    """Build and return an ezdxf Drawing (shared by DXF & DWG generators)."""
    polyline_codes = polyline_codes or []

    doc = ezdxf.new("R2018")
    doc.units = UNITS_MAP.get(units, 6)
    msp = doc.modelspace()

    doc.header['$PDMODE'] = 2
    doc.header['$PDSIZE'] = text_height * 0.5
    doc.styles.add("SURVEY", font="simplex.shx")

    # Layers — Annotation Standards v1.0
    for name, color in [("MS POINT", 7), ("POINT_NUMBER", 130),
                        ("ELEVATION", 2), ("DESCRIPTION", 130)]:
        doc.layers.add(name, color=color)

    for r in rows:
        sr_no = str(r.get("sr_no", "")).strip()
        n, e = float(r["northing"]), float(r["easting"])
        elev = r.get("elevation")
        desc = r.get("description")
        if desc is not None and not str(desc).strip():
            desc = None
        z = float(elev) if elev is not None else 0.0
        sr_pos, desc_pos, elev_pos = label_positions(e, n, text_height)

        msp.add_point((e, n, z), dxfattribs={"layer": "MS POINT"})
        msp.add_text(sr_no, dxfattribs={
            "layer": "POINT_NUMBER", "height": text_height,
            "style": "SURVEY", "insert": (*sr_pos, 0),
        })
        if desc:
            msp.add_text(str(desc), dxfattribs={
                "layer": "DESCRIPTION", "height": text_height,
                "style": "SURVEY", "insert": (*desc_pos, 0),
            })
        if elev is not None:
            try:
                msp.add_text(f"{float(elev):.3f}", dxfattribs={
                    "layer": "ELEVATION", "height": text_height,
                    "style": "SURVEY", "insert": (*elev_pos, 0),
                })
            except (ValueError, TypeError):
                pass

    # Polylines
    for code in polyline_codes:
        pts = [(float(r["easting"]), float(r["northing"]))
               for r in rows
               if r.get("description") and str(r["description"]).strip() == str(code).strip()]
        if len(pts) < 2:
            continue
        ln = f"PLINE_{clean_code(str(code))}"
        if doc.layers.get(ln) is None:
            doc.layers.add(ln, color=3)
        msp.add_lwpolyline(pts, dxfattribs={"layer": ln, "closed": False})

    return doc


def generate_dxf_stream(rows, text_height=1.0, offset=True,
                        polyline_codes=None, units="meters"):
    """Generate a DXF file and return as an in-memory BytesIO stream."""
    doc = generate_dxf_doc(rows, text_height, offset, polyline_codes, units)
    s = io.StringIO()
    doc.write(s)
    return io.BytesIO(s.getvalue().encode("utf-8"))
