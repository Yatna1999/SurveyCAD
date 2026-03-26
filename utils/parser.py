"""
parser.py – CSV/TXT survey-data parser.
Auto-detects encoding (chardet) and delimiter (comma > tab > semicolon > space).
Columns: Sr_No | Northing | Easting | Elevation? | Description?
"""

import csv, io, logging
import chardet

logger = logging.getLogger(__name__)


def _to_float(v):
    try:
        return float(v.strip())
    except (ValueError, AttributeError):
        return None


def _detect_delim(sample):
    counts = {",": sample.count(","), "\t": sample.count("\t"), ";": sample.count(";")}
    best = max(counts, key=counts.get)
    return best if counts[best] else " "


def _is_header(cell):
    """True if `cell` looks like a column label (alphabetic, no digits)."""
    cell = cell.strip()
    if not cell:
        return False
    try:
        float(cell); return False
    except ValueError:
        pass
    return not any(ch.isdigit() for ch in cell)


def parse_content(raw_bytes: bytes):
    """Parse raw file bytes → (rows: list[dict], warnings: list[str])."""
    warnings = []
    if not raw_bytes:
        return [], warnings

    # Decode
    det = chardet.detect(raw_bytes[:51200])
    enc = det.get("encoding") or "utf-8"
    logger.info("Encoding: %s (%.0f%%)", enc, (det.get("confidence", 0)) * 100)
    content = raw_bytes.decode(enc, errors="replace")
    if not content.strip():
        return [], warnings

    # Delimiter
    delim = _detect_delim("\n".join(content.splitlines()[:10]))
    logger.info("Delimiter: %r", delim)

    # Parse rows
    rows = []
    first = True
    for ln, raw_row in enumerate(csv.reader(io.StringIO(content), delimiter=delim), 1):
        row = [c.strip() for c in raw_row]
        if not any(row) or len(row) < 3:
            continue

        if first:
            first = False
            if _is_header(row[0]):
                logger.info("Header at line %d – skipping.", ln)
                continue

        northing = _to_float(row[1])
        easting = _to_float(row[2])
        if northing is None or easting is None:
            if _is_header(row[0]):
                warnings.append(f"Line {ln}: skipped alphabetic row '{row[0]}'.")
            continue

        elev_raw = row[3] if len(row) > 3 else ""
        desc_raw = row[4] if len(row) > 4 else ""

        rows.append({
            "sr_no":       row[0].strip(),
            "northing":    northing,
            "easting":     easting,
            "elevation":   _to_float(elev_raw) if elev_raw.strip() else None,
            "description": desc_raw.strip() or None,
        })

    logger.info("Parsed %d valid rows", len(rows))
    return rows, warnings
