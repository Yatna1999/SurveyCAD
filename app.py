"""
app.py – SurveyCAD
Flask backend: upload CSV/TXT → generate SCR / DXF / DWG.
"""

import os, logging, io, uuid

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS

from utils.parser import parse_content
from utils.scr_generator import generate_scr_stream
from utils.dxf_generator import generate_dxf_stream
from utils.dwg_generator import generate_dwg_stream

# ── App Setup ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))
CORS(app)
app.config.update(MAX_CONTENT_LENGTH=10 * 1024 * 1024,
                  TEMPLATES_AUTO_RELOAD=True, SEND_FILE_MAX_AGE_DEFAULT=0)
app.jinja_env.auto_reload = True

ALLOWED_EXT = frozenset({"csv", "txt"})
VALID_UNITS = ("meters", "millimeters", "feet")

GENERATORS = {
    "scr": (generate_scr_stream, "text/plain"),
    "dxf": (generate_dxf_stream, "application/dxf"),
    "dwg": (generate_dwg_stream, "application/octet-stream"),
}


# ── Helpers ──────────────────────────────────────────────────────

def _ext_ok(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _upload_err(msg):
    return jsonify(success=False, rows=[], row_count=0,
                   unique_codes=[], has_elevation=False,
                   has_description=False, errors=[msg]), 400


def _unique_codes(rows):
    seen, out = set(), []
    for r in rows:
        d = r.get("description")
        if d and d not in seen:
            seen.add(d); out.append(d)
    return out


# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(running=True, message="SurveyCAD is running.")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return _upload_err("No file part in request.")
    f = request.files["file"]
    if not f.filename:
        return _upload_err("No file selected.")
    if not _ext_ok(f.filename):
        return _upload_err("Only .csv and .txt files are accepted.")

    raw = f.read()
    if b'\x00' in raw[:512]:
        return _upload_err("Invalid file: binary content detected.")

    errors, warnings = [], []
    try:
        rows, warnings = parse_content(raw)
    except Exception as exc:
        logger.exception("Parse error"); errors.append(str(exc)); rows = []

    if not rows and not errors:
        errors.append("No valid rows could be parsed from the file.")

    return jsonify(
        success=len(rows) > 0, rows=rows, row_count=len(rows),
        unique_codes=_unique_codes(rows),
        has_elevation=any(r.get("elevation") is not None for r in rows),
        has_description=any(r.get("description") is not None for r in rows),
        errors=errors, warnings=warnings,
    )


@app.route("/api/generate-<fmt>", methods=["POST"])
def api_generate(fmt):
    """Unified generation endpoint for scr / dxf / dwg."""
    if fmt not in GENERATORS:
        return jsonify(error="Unknown format."), 404

    try:
        body = request.get_json(force=True, silent=True) or {}
        rows = body.get("rows")
        if not rows:
            return jsonify(error="No survey data provided"), 400
        if len(rows) > 5000:
            return jsonify(error="Row count exceeds 5000 limit."), 400

        th = max(0.1, min(float(body.get("text_height", 1.0)), 10000.0))
        units = str(body.get("units", "meters")).lower()
        if units not in VALID_UNITS:
            units = "meters"

        gen_fn, mime = GENERATORS[fmt]
        kwargs = dict(rows=rows, text_height=th, offset=True,
                      polyline_codes=body.get("polyline_codes", []))
        if fmt != "scr":
            kwargs["units"] = units

        stream = gen_fn(**kwargs)
        stream.seek(0)
        sid = uuid.uuid4().hex[:8]
        return send_file(stream, as_attachment=True,
                         download_name=f"survey_{sid}.{fmt}", mimetype=mime)
    except Exception as exc:
        logger.exception("%s generation failed", fmt.upper())
        return jsonify(error=str(exc)), 500


# ── Entry Point ──────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("=" * 54)
    logger.info("  SurveyCAD  |  Made by Yatna Patel")
    logger.info("  http://0.0.0.0:%d", port)
    logger.info("=" * 54)
    app.run(host="0.0.0.0", port=port, debug=False)
