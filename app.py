"""
app.py - SurveyCAD
Flask backend entry point.

Routes:
    GET  /                          -> serves index.html
    GET  /api/status                -> health check
    POST /api/upload                -> parse CSV/TXT, return row data
    POST /api/generate              -> generate SCR and/or DXF files
    GET  /api/download/<filename>   -> download from output/ folder
"""

import os
import logging
import tempfile
import threading

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS

# ---------------------------------------------------------------------------
# App setup – explicit template and static folder paths
# ---------------------------------------------------------------------------
BASE_DIR:     str = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR: str = os.path.join(BASE_DIR, "templates")
STATIC_DIR:   str = os.path.join(BASE_DIR, "static")
OUTPUT_DIR:   str = os.path.join(BASE_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)
CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max upload limit

# Create output directory on startup
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Generator imports (non-fatal if missing)
# ---------------------------------------------------------------------------
from utils.scr_generator import generate_scr
from utils.dxf_generator import generate_dxf
from utils.parser import parse_file

# ---------------------------------------------------------------------------
# In-memory storage (no database)
# ---------------------------------------------------------------------------
_store_lock: threading.Lock = threading.Lock()
_parsed_rows: list[dict] = []
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"csv", "txt"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allowed_file(filename: str) -> bool:
    """Check if the provided filename has an approved extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _unique_codes(rows: list[dict]) -> list[str]:
    """Return a list of unique description codes from the rows."""
    seen: set[str] = set()
    codes: list[str] = []
    for row in rows:
        desc = row.get("description")
        if desc and desc not in seen:
            seen.add(desc)
            codes.append(desc)
    return codes


def _has_elevation(rows: list[dict]) -> bool:
    """Check if any row in the dataset contains elevation data."""
    return any(r.get("elevation") is not None for r in rows)


def _has_description(rows: list[dict]) -> bool:
    """Check if any row in the dataset contains a description."""
    return any(r.get("description") is not None for r in rows)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Serve the main UI."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """Health-check endpoint."""
    return jsonify({"running": True, "message": "SurveyCAD is running."})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Accept a multipart file upload (csv or txt), parse it, and return
    a summary of the parsed data.
    """
    global _parsed_rows
    errors: list[str] = []
    rows: list[dict] = []

    if "file" not in request.files:
        return jsonify({"success": False, "rows": [], "row_count": 0,
                        "unique_codes": [], "has_elevation": False,
                        "has_description": False,
                        "errors": ["No file part in request."]}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"success": False, "rows": [], "row_count": 0,
                        "unique_codes": [], "has_elevation": False,
                        "has_description": False,
                        "errors": ["No file selected."]}), 400

    if not _allowed_file(file.filename):
        return jsonify({"success": False, "rows": [], "row_count": 0,
                        "unique_codes": [], "has_elevation": False,
                        "has_description": False,
                        "errors": ["Only .csv and .txt files are accepted."]}), 400

    # Save to a temporary directory, parse, then auto-cleanup on exit
    suffix: str = os.path.splitext(file.filename)[1]
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "upload" + suffix)
            file.save(tmp_path)
            rows = parse_file(tmp_path)
    except Exception as exc:
        logger.exception("Error during file parse")
        errors.append(str(exc))

    if not rows and not errors:
        errors.append("No valid rows could be parsed from the file.")

    with _store_lock:
        _parsed_rows = rows

    return jsonify({
        "success":         len(rows) > 0,
        "rows":            rows,
        "row_count":       len(rows),
        "unique_codes":    _unique_codes(rows),
        "has_elevation":   _has_elevation(rows),
        "has_description": _has_description(rows),
        "errors":          errors,
    })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Generate SCR and/or DXF files from survey rows.

    Expected JSON body::

        {
            "rows":            list of row dicts  (full array from upload response)
            "mode":            "scr" | "dxf"      (string OR list, OR use "modes")
            "modes":           ["scr", "dxf"]     (preferred key; fallback to "mode")
            "text_height":     float   default 1.0
            "offset":          bool    default true
            "polyline_codes":  [str]   default []
            "units":           str     default "meters"
        }

    Returns::

        {
            "success": bool,
            "files":   [{"name": str, "size_bytes": int}],
            "logs":    [str],
            "errors":  [str]
        }
    """
    global _parsed_rows

    logs:   list[str] = []
    errors: list[str] = []
    files:  list[dict] = []

    try:
        body: dict = request.get_json(force=True, silent=True) or {}

        # --- Rows: prefer body rows, fall back to in-memory ---
        with _store_lock:
            rows = body.get("rows")
            if not rows:
                rows = _parsed_rows

        if not rows:
            return jsonify({
                "success": False, "files": [], "logs": [],
                "errors": ["No data available. Please upload a file first."],
            }), 400

        if len(rows) > 5000:
            return jsonify({
                "success": False, "files": [], "logs": [],
                "errors": ["Row count exceeds 5000 limit."],
            }), 400

        logs.append(f"Received {len(rows)} survey points.")

        # --- Mode: accept both 'modes' (list) and 'mode' (str or list) ---
        raw = body.get("modes") or body.get("mode", "scr")
        modes: list[str] = list(raw) if isinstance(raw, list) else [str(raw)]
        valid_modes: list[str] = [m for m in modes if m in ("scr", "dxf")]
        if not valid_modes:
            return jsonify({
                "success": False, "files": [], "logs": [],
                "errors": ["Invalid output mode provided. Must be 'scr' and/or 'dxf'."],
            }), 400
        logs.append(f"Output mode(s): {', '.join(m.upper() for m in valid_modes)}")

        # --- Parameters ---
        try:
            text_height: float = max(0.1, float(body.get("text_height", 1.0)))
        except (ValueError, TypeError):
            text_height = 1.0

        offset: bool         = bool(body.get("offset", True))
        polyline_codes: list = body.get("polyline_codes", [])
        if not isinstance(polyline_codes, list):
            polyline_codes = []

        units: str = str(body.get("units", "meters")).lower()
        if units not in ("meters", "millimeters", "feet"):
            units = "meters"

        logs.append(f"Text height: {text_height}  |  Units: {units}  |  Offset: {offset}")
        if polyline_codes:
            logs.append(f"Polylines requested for: {', '.join(str(c) for c in polyline_codes)}")

        # --- Generate SCR ---
        if "scr" in valid_modes:
            scr_path: str = os.path.join(OUTPUT_DIR, "survey_output.scr")
            try:
                logs.append("Building SCR layer setup block\u2026")
                generate_scr(
                    rows=rows,
                    output_path=scr_path,
                    text_height=text_height,
                    offset=offset,
                    polyline_codes=polyline_codes,
                )
                size: int = os.path.getsize(scr_path)
                files.append({"name": "survey_output.scr", "size_bytes": size})
                logs.append(f"SCR written: {len(rows)} point commands, {size} bytes.")
                logger.info("SCR file generated: %s (%d bytes)", scr_path, size)
            except Exception as exc:
                logger.exception("SCR generation failed")
                errors.append(f"SCR error: {exc}")
                logs.append(f"SCR generation failed: {exc}")

        # --- Generate DXF ---
        if "dxf" in valid_modes:
            dxf_path: str = os.path.join(OUTPUT_DIR, "survey_output.dxf")
            try:
                logs.append("Building DXF entity model\u2026")
                generate_dxf(
                    rows=rows,
                    output_path=dxf_path,
                    text_height=text_height,
                    offset=offset,
                    polyline_codes=polyline_codes,
                    units=units,
                )
                size = os.path.getsize(dxf_path)
                files.append({"name": "survey_output.dxf", "size_bytes": size})
                logs.append(f"DXF written: {len(rows)} entities, {size} bytes.")
                logger.info("DXF file generated: %s (%d bytes)", dxf_path, size)
            except Exception as exc:
                logger.exception("DXF generation failed")
                errors.append(f"DXF error: {exc}")
                logs.append(f"DXF generation failed: {exc}")

        success: bool = len(files) > 0
        if success:
            logs.append("Done! Files are ready for download.")

        return jsonify({
            "success": success,
            "files":   files,
            "logs":    logs,
            "errors":  errors,
        })

    except Exception as exc:
        logger.exception("Unexpected error in /api/generate")
        return jsonify({
            "success": False,
            "files":   [],
            "logs":    logs,
            "errors":  [str(exc)],
        }), 500


@app.route("/api/download/<path:filename>", methods=["GET"])
def api_download(filename: str):
    """Serve a file from the output folder as a download attachment."""
    ALLOWED_DOWNLOADS: frozenset[str] = frozenset({"survey_output.scr", "survey_output.dxf"})
    safe_name: str = os.path.basename(filename)
    if safe_name not in ALLOWED_DOWNLOADS:
        return jsonify({"error": "File not found."}), 404

    file_path: str = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found."}), 404

    return send_from_directory(OUTPUT_DIR, safe_name, as_attachment=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=" * 54)
    logger.info("  SurveyCAD  |  Made by Yatna Patel")
    logger.info("  http://127.0.0.1:5000")
    logger.info("  Output folder: %s", OUTPUT_DIR)
    logger.info("=" * 54)
    app.run(host="127.0.0.1", port=5000, debug=False)
