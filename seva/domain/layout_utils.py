from __future__ import annotations

from typing import Any, Mapping

FLAG_DEFAULTS: tuple[str, ...] = (
    "run_cv",
    "run_dc",
    "run_ac",
    "run_eis",
    "run_lsv",
    "run_cdl",
    "eval_cdl",
)


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


def with_flag_defaults(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return a snapshot dict with flag keys defaulted to "0"."""
    normalized = dict(snapshot or {})
    for flag in FLAG_DEFAULTS:
        normalized.setdefault(flag, "0")
    return normalized


__all__ = ["FLAG_DEFAULTS", "normalize_selection", "with_flag_defaults"]
