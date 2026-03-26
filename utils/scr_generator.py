"""SCR (AutoCAD script) generator for SurveyCAD."""

import io, logging
from utils.geometry import clean_code, label_positions

logger = logging.getLogger(__name__)

_C = lambda e, n: f"{e:.4f},{n:.4f}"
_S = lambda v: str(v).replace('\r', ' ').replace('\n', ' ').strip()


def _set_layer(lines, name):
    lines += ["_-LAYER", "S", name, ""]


def _add_text(lines, pos, height, content):
    lines += ["-TEXT", _C(pos[0], pos[1]), f"{height:.4f}", "0", _S(content)]


def generate_scr_stream(rows, text_height=1.0, offset=True, polyline_codes=None):
    """Generate an AutoCAD SCR script from parsed survey rows."""
    polyline_codes = polyline_codes or []
    L = []

    # 1. Layer setup — Annotation Standards v1.0
    L += ["_-LAYER", "N", "MS POINT,POINT_NUMBER,ELEVATION,DESCRIPTION",
          "C", "7", "MS POINT",
          "C", "130", "POINT_NUMBER",
          "C", "2", "ELEVATION",
          "C", "130", "DESCRIPTION", ""]

    # Point shape: Plus (+) = PDMODE 2, size = 0.5 × text_height
    L += ["PDMODE", "2", "PDSIZE", f"{text_height * 0.5:.4f}"]

    # 2. Points
    _set_layer(L, "MS POINT")
    for r in rows:
        L += ["POINT", _C(float(r["easting"]), float(r["northing"]))]

    # 3. Point numbers
    _set_layer(L, "POINT_NUMBER")
    for r in rows:
        e, n = float(r["easting"]), float(r["northing"])
        sr, _, _ = label_positions(e, n, text_height)
        _add_text(L, sr, text_height, r.get("sr_no", ""))

    # 4. Descriptions
    _set_layer(L, "DESCRIPTION")
    for r in rows:
        desc = r.get("description")
        if not desc or not str(desc).strip():
            continue
        e, n = float(r["easting"]), float(r["northing"])
        _, dp, _ = label_positions(e, n, text_height)
        _add_text(L, dp, text_height, desc)

    # 5. Elevations
    _set_layer(L, "ELEVATION")
    for r in rows:
        elev = r.get("elevation")
        if elev is None:
            continue
        e, n = float(r["easting"]), float(r["northing"])
        _, _, ep = label_positions(e, n, text_height)
        _add_text(L, ep, text_height, f"{float(elev):.3f}")

    # 6. Polylines
    for code in polyline_codes:
        cs = _S(str(code))
        pts = [r for r in rows if str(r.get("description", "")).strip() == cs]
        if len(pts) < 2:
            continue
        ln = f"PLINE_{clean_code(cs)}"
        L += ["_-LAYER", "N", ln, "C", "3", ln, "S", ln, ""]
        L.append("PLINE")
        for p in pts:
            L.append(_C(float(p["easting"]), float(p["northing"])))
        L.append("")

    # 7. Zoom extents
    L += ["ZOOM", "E", ""]

    return io.BytesIO(("\r\n".join(L) + "\r\n").encode("utf-8"))
