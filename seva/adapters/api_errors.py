"""Typed adapter error model and payload parsing utilities.

REST adapters use these helpers to convert transport failures into stable
exceptions consumed by use-case level error mapping.
"""

from __future__ import annotations

from typing import Any, Optional


class ApiError(RuntimeError):
    """Base class for REST adapter failures."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        payload: Any = None,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.hint = hint
        self.payload = payload
        self.context = context


class ApiClientError(ApiError):
    """HTTP 4xx from the Box API."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        payload: Any = None,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            status=status,
            code=code,
            hint=hint,
            payload=payload,
            context=context,
        )


class ApiServerError(ApiError):
    """HTTP 5xx from the Box API."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        payload: Any = None,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            status=status,
            payload=payload,
            context=context,
        )


class ApiTimeoutError(ApiError):
    """Transport level timeout or connectivity failure."""

    def __init__(
        self,
        message: str,
        *,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(message, context=context)


def parse_error_payload(resp: Any) -> Any:
    """Best-effort extraction of error payload without raising."""
    try:
        return resp.json()
    except Exception:
        snippet = getattr(resp, "text", "")
        if not snippet:
            return None
        return snippet[:400]


def build_error_message(ctx: str, status: int, payload: Any) -> str:
    """Build a human-readable adapter error message from payload details.
    
    Args:
        ctx (str): Input provided by the caller.
        status (int): Input provided by the caller.
        payload (Any): Input provided by the caller.
    
    Returns:
        str: Value returned to the caller.
    
    Raises:
        RuntimeError: Raised when payload normalization fails.
    """
    detail = _payload_detail(payload)
    hint = extract_error_hint(payload)
    if detail and hint and hint != detail:
        return f"{ctx}: {detail} (HTTP {status}) Hint: {hint}"
    if detail:
        return f"{ctx}: {detail} (HTTP {status})"
    if hint:
        return f"{ctx}: {hint} (HTTP {status})"
    return f"{ctx}: HTTP {status}"


def extract_error_code(payload: Any) -> Optional[str]:
    """Extract a stable error code from API error payloads.
    
    Args:
        payload (Any): Input provided by the caller.
    
    Returns:
        Optional[str]: Value returned to the caller.
    
    Raises:
        RuntimeError: Raised when payload normalization fails.
    """
    if isinstance(payload, dict):
        value = payload.get("code") or payload.get("error_code")
        if value is None:
            return None
        return value if isinstance(value, str) else str(value)
    return None


def extract_error_hint(payload: Any) -> Optional[str]:
    """Extract a user-facing hint from API error payloads.
    
    Args:
        payload (Any): Input provided by the caller.
    
    Returns:
        Optional[str]: Value returned to the caller.
    
    Raises:
        RuntimeError: Raised when payload normalization fails.
    """
    if isinstance(payload, dict):
        value = payload.get("hint") or payload.get("details") or payload.get("message")
        return _payload_detail(value)
    if isinstance(payload, str):
        return payload.strip() or None
    return None


def _payload_detail(payload: Any) -> Optional[str]:
    """Extract the best available text detail from dynamic payload shapes.
    
    Args:
        payload (Any): Input provided by the caller.
    
    Returns:
        Optional[str]: Value returned to the caller.
    
    Raises:
        RuntimeError: Raised when payload normalization fails.
    """
    if payload is None:
        return None
    if isinstance(payload, str):
        text = payload.strip()
        return text or None
    if isinstance(payload, dict):
        for key in ("detail", "message", "error", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
