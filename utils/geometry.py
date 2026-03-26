"""Shared geometry helpers for SurveyCAD generators."""

import re


def clean_code(code: str) -> str:
    """Sanitise a description for use as an AutoCAD layer name."""
    return re.sub(r"[^\w]", "_", code).upper()


def label_positions(easting, northing, text_height):
    """Return (sr_no, description, elevation) label positions per Annotation Standards v1.0."""
    gap = text_height
    rise = text_height * 1.5
    return (
        (easting + gap, northing + rise),   # sr_no:       top-right
        (easting + gap, northing),           # description: mid-right
        (easting + gap, northing - rise),    # elevation:   bottom-right
    )
