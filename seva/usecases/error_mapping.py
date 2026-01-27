from __future__ import annotations

"""Translate adapter errors into user-facing UseCaseError instances."""

from typing import Any, Optional

from seva.adapters.api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    ApiTimeoutError,
    extract_error_hint,
)
from seva.domain.ports import UseCaseError


def map_api_error(
    exc: Exception,
    *,
    default_code: str,
    default_message: Optional[str] = None,
) -> UseCaseError:
    if isinstance(exc, UseCaseError):
        return exc
    if isinstance(exc, ApiTimeoutError):
        return UseCaseError("REQUEST_TIMEOUT", "Request timed out. Check connection.")
    if isinstance(exc, ApiClientError):
        status = exc.status or 0
        hint = exc.hint or extract_error_hint(getattr(exc, "payload", None))
        if status == 422:
            return UseCaseError(
                "INVALID_PARAMS",
                _compose_error_message("Invalid parameters", hint),
            )
        if status == 409:
            slot_hint = _extract_slot_hint(exc)
            message = _compose_error_message("Slot busy", slot_hint or hint)
            meta = {"busy_wells": [slot_hint]} if slot_hint else None
            return UseCaseError("SLOT_BUSY", message, meta=meta)
        if status in (401, 403):
            return UseCaseError("AUTH_FAILED", "Auth failed / API key invalid.")
        label = f"Request failed (HTTP {status})" if status else "Request failed"
        return UseCaseError("REQUEST_FAILED", _compose_error_message(label, hint))
    if isinstance(exc, ApiServerError):
        return UseCaseError("SERVER_ERROR", "Box error, try again.")
    if isinstance(exc, ApiError):
        return UseCaseError("API_ERROR", str(exc))

    message = default_message or str(exc) or "Unexpected error."
    return UseCaseError(default_code, message)


def _compose_error_message(base: str, hint: Optional[str]) -> str:
    hint_text = (hint or "").strip()
    if hint_text:
        return f"{base}: {hint_text}"
    if base.endswith("."):
        return base
    return f"{base}."


def _extract_slot_hint(err: ApiClientError) -> Optional[str]:
    payload = getattr(err, "payload", None)
    slot = _find_slot(payload)
    if slot:
        return slot
    hint = err.hint or extract_error_hint(payload)
    if hint:
        cleaned = hint.replace(",", " ").replace(";", " ")
        for token in cleaned.split():
            lower = token.lower()
            if lower.startswith("slot"):
                parts = token.split("=", 1)
                return parts[1] if len(parts) == 2 else token
    return None


def _find_slot(data: Any) -> Optional[str]:
    if isinstance(data, dict):
        for key in ("slot", "slot_id", "well", "well_id"):
            value = data.get(key)
            if value:
                return str(value)
        for value in data.values():
            slot = _find_slot(value)
            if slot:
                return slot
    elif isinstance(data, list):
        for item in data:
            slot = _find_slot(item)
            if slot:
                return slot
    return None


__all__ = ["map_api_error"]
