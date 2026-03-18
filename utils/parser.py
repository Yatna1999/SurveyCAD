"""
utils/parser.py
CSV/TXT file parser for SurveyCAD.

Columns (no header row):
    Col 0: Sr_No       (str) - numeric or text like 'RTCM-Ref 3700'
    Col 1: Northing    (float) - always present
    Col 2: Easting     (float) - always present
    Col 3: Elevation   (float|None) - may be empty
    Col 4: Description (str|None)  - may be empty

Delimiter: auto-detected (comma, tab, semicolon, space)
Encoding:  auto-detected via chardet
"""

import csv
import io
import os
import re
import logging

import chardet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_encoding(filepath: str) -> str:
    """Read raw bytes and use chardet to detect file encoding."""
    with open(filepath, "rb") as f:
        raw = f.read()
    result = chardet.detect(raw)
    encoding = result.get("encoding") or "utf-8"
    logger.info("Detected encoding: %s (confidence %.2f)", encoding, result.get("confidence", 0))
    return encoding


def _detect_delimiter(sample: str) -> str:
    """
    Detect the most likely delimiter from a sample of the file content.
    Priority: comma > tab > semicolon > space.
    """
    candidates = {
        ",": sample.count(","),
        "\t": sample.count("\t"),
        ";": sample.count(";"),
    }
    # Only fall back to space if no other delimiter found
    best = max(candidates, key=candidates.get)
    if candidates[best] == 0:
        return " "
    return best


def _is_header_row(first_cell: str) -> bool:
    """
    Return True if the first cell looks like a header label rather than data.
    Data Sr_No values are either:
      - purely numeric (e.g. '1', '2.0')
      - RTCM-style: starts with letters but contains digits (e.g. 'RTCM-Ref 3700')
    A header row first cell is plain alphabetic text with no digits.
    """
    cell = first_cell.strip()
    if not cell:
        return False
    # If purely numeric → data row
    try:
        float(cell)
        return False
    except ValueError:
        pass
    # If it contains at least one digit → treat as RTCM-style sr_no → data row
    if any(ch.isdigit() for ch in cell):
        return False
    # Plain alphabetic / symbolic text → header
    return True


def _parse_float(value: str):
    """Return float or None if conversion fails."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(filepath: str) -> list:
    """
    Parse a CSV or TXT survey file.

    Returns a list of dicts:
        {
            sr_no:      str,
            northing:   float,
            easting:    float,
            elevation:  float | None,
            description: str | None,
        }

    Returns an empty list if the file cannot be read.
    """
    if not os.path.isfile(filepath):
        logger.error("File not found: %s", filepath)
        return []

    # --- Detect encoding ---
    try:
        encoding = _detect_encoding(filepath)
    except Exception as exc:
        logger.error("Encoding detection failed: %s", exc)
        encoding = "utf-8"

    # --- Read file content ---
    try:
        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            content = f.read()
    except Exception as exc:
        logger.error("Cannot read file %s: %s", filepath, exc)
        return []

    if not content.strip():
        logger.warning("File is empty: %s", filepath)
        return []

    # --- Detect delimiter from first few lines ---
    sample = "\n".join(content.splitlines()[:10])
    delimiter = _detect_delimiter(sample)
    logger.info("Detected delimiter: %r", delimiter)

    # --- Parse with csv reader ---
    rows = []
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    first_data_row = True

    for line_num, raw_row in enumerate(reader, start=1):
        # Strip whitespace from every cell
        row = [cell.strip() for cell in raw_row]

        # Skip completely empty rows
        if not any(row):
            continue

        # Need at least 3 columns: Sr_No, Northing, Easting
        if len(row) < 3:
            logger.debug("Line %d skipped (fewer than 3 columns): %s", line_num, row)
            continue

        # Check for header row on first non-empty data row
        if first_data_row:
            first_data_row = False
            if _is_header_row(row[0]):
                logger.info("Header row detected at line %d – skipping.", line_num)
                continue

        # --- Extract columns ---
        sr_no_raw   = row[0]
        northing_raw = row[1]
        easting_raw  = row[2]
        elevation_raw = row[3] if len(row) > 3 else ""
        description_raw = row[4] if len(row) > 4 else ""

        # Northing and Easting must be valid floats
        northing = _parse_float(northing_raw)
        easting  = _parse_float(easting_raw)

        if northing is None or easting is None:
            logger.debug(
                "Line %d skipped – cannot parse northing/easting: %r / %r",
                line_num, northing_raw, easting_raw,
            )
            continue

        # Sr_No: keep as string, strip whitespace
        sr_no = sr_no_raw.strip()

        # Elevation: None if empty or unparseable
        elevation = None
        if elevation_raw.strip():
            elevation = _parse_float(elevation_raw)
            # If it can't be converted, treat as None silently

        # Description: None if empty
        description = description_raw.strip() if description_raw.strip() else None

        rows.append({
            "sr_no":       sr_no,
            "northing":    northing,
            "easting":     easting,
            "elevation":   elevation,
            "description": description,
        })

    logger.info("Parsed %d valid rows from %s", len(rows), filepath)
    return rows
