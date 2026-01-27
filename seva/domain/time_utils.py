from __future__ import annotations

"""Datetime parsing helpers for client-provided timestamps."""

from datetime import datetime
from typing import Any, Optional


def parse_client_datetime(value: Any) -> datetime:
    """Parse client datetime overrides into a timezone-aware datetime."""
    if isinstance(value, dict):
        raw = value.get("value") or value.get("iso") or value.get("client_dt")
        value = raw if raw is not None else value

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            parsed = datetime.now().astimezone().replace(microsecond=0)
        else:
            normalized = text.replace(" ", "T")
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            if "T" in normalized:
                date_part, time_part = normalized.split("T", 1)
                if ":" not in time_part:
                    time_part = time_part.replace("-", ":")
                normalized = f"{date_part}T{time_part}"
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError:
                parsed = _parse_with_fallback(text)

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        local_zone = datetime.now().astimezone().tzinfo
        parsed = parsed.replace(tzinfo=local_zone)

    return parsed.astimezone().replace(microsecond=0)


def _parse_with_fallback(text: str) -> datetime:
    fallback_formats = (
        "%Y-%m-%d_%H-%M-%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H-%M-%S",
    )
    for fmt in fallback_formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.now().astimezone().replace(microsecond=0)


__all__ = ["parse_client_datetime"]
