"""Formatting helpers for normalized status labels in the UI layer.

Views and view models use these functions to convert backend/domain status keys
into consistent labels for operators.
"""

from __future__ import annotations

from typing import Optional


def phase_key(phase: Optional[str]) -> str:
    """Normalize phase text into a lowercase status token.
    
    Args:
        phase (Optional[str]): Input provided by the caller.
    
    Returns:
        str: Value returned to the caller.
    
    Raises:
        ValueError: Raised when status or configuration values are invalid.
    """
    return (phase or "").strip().lower()


def phase_label(phase: Optional[str]) -> str:
    """Convert normalized status keys into operator-facing labels.
    
    Args:
        phase (Optional[str]): Input provided by the caller.
    
    Returns:
        str: Value returned to the caller.
    
    Raises:
        ValueError: Raised when status or configuration values are invalid.
    """
    key = phase_key(phase)
    mapping = {
        "failed": "Failed",
        "error": "Error",
        "running": "Running",
        "queued": "Queued",
        "done": "Done",
        "canceled": "Canceled",
        "cancelled": "Canceled",
        "idle": "Idle",
    }
    if not key:
        return "Idle"
    if key in mapping:
        return mapping[key]
    cleaned = key.replace("_", " ").replace("-", " ")
    return cleaned.title()


def registry_status_label(status: Optional[str], *, downloaded: bool) -> str:
    """Format registry status strings with download-state context.
    
    Args:
        status (Optional[str]): Input provided by the caller.
        downloaded (bool): Input provided by the caller.
    
    Returns:
        str: Value returned to the caller.
    
    Raises:
        ValueError: Raised when status or configuration values are invalid.
    """
    key = phase_key(status)
    if key == "done":
        return "Done (Downloaded)" if downloaded else "Done"
    if key == "cancelled":
        return "Cancelled"
    if key == "error":
        return "Error"
    if key == "deleted":
        return "Deleted"
    return "Running"


__all__ = ["phase_key", "phase_label", "registry_status_label"]
