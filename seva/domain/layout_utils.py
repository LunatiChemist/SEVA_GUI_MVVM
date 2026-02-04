"""Helpers for normalizing plate-layout selection payloads.

View models use these utilities before passing layout data into use cases.
"""

from __future__ import annotations

from typing import Any, Mapping

def normalize_selection(selection: Any) -> list[str]:
    """Normalize selection inputs into a unique list of well identifiers."""
    normalized: list[str] = []
    if selection is None:
        return normalized
    if isinstance(selection, str):
        items = [selection]
    elif isinstance(selection, (list, tuple, set)):
        items = selection
    else:
        items = [selection]
    for item in items:
        token = str(item).strip()
        if token and token not in normalized:
            normalized.append(token)
    return normalized


__all__ = ["normalize_selection"]
