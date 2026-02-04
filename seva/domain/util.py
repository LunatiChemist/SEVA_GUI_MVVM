"""Small domain utility functions used across planning and adapters.

These helpers keep common normalization rules centralized and testable.
"""

from __future__ import annotations

from typing import Optional


def well_id_to_box(well_id: str) -> Optional[str]:
    """
    Extract the box identifier from a well id string.

    Returns the leading alphabetical character in uppercase when present,
    else None for malformed inputs.
    """
    if not isinstance(well_id, str):
        return None
    text = well_id.strip()
    if not text:
        return None
    first = text[0]
    if not first.isalpha():
        return None
    return first.upper()


def normalize_mode_name(mode: str) -> str:
    """Return a normalized mode token for backend payloads."""
    if mode is None:
        return ""
    token = str(mode).strip().upper()
    if token == "AC":
        return "CA"
    return token


__all__ = ["normalize_mode_name", "well_id_to_box"]
