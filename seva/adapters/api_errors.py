"""Typed adapter error classes and error-payload helpers.

This module defines the adapter-layer exception taxonomy used by HTTP adapters
before use cases translate those failures into ``UseCaseError`` instances.

Dependencies:
    No external dependencies beyond Python typing primitives.

Call context:
    - Raised by REST adapters in ``seva/adapters/*.py``.
    - Read by ``seva/usecases/error_mapping.py`` for user-facing translation.
"""

from __future__ import annotations

from typing import Any, Optional


class ApiError(RuntimeError):
    """Base exception for adapter failures.

    Attributes:
        status: Optional HTTP status code when available.
        code: Optional backend-provided stable error code.
        hint: Optional backend-provided user guidance.
        payload: Original parsed payload (dict/string/other) for diagnostics.
        context: Call-site identifier such as ``start[box1]``.
    """

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
        """Initialize a base adapter error.

        Args:
            message: Human-readable summary.
            status: HTTP status code when available.
            code: Stable backend error code when available.
            hint: Optional user-facing hint text.
            payload: Parsed response payload for diagnostics.
            context: Adapter context string identifying the failing operation.
        """
        super().__init__(message)
        self.status = status
        self.code = code
        self.hint = hint
        self.payload = payload
        self.context = context


class ApiClientError(ApiError):
    """Adapter error for client-side HTTP failures (4xx)."""

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
        """Initialize a 4xx adapter error.

        Args:
            message: Human-readable summary.
            status: HTTP status code in the 4xx range.
            code: Stable backend error code when available.
            hint: Optional user-facing hint text.
            payload: Parsed response payload for diagnostics.
            context: Adapter context string identifying the failing operation.
        """
        super().__init__(
            message,
            status=status,
            code=code,
            hint=hint,
            payload=payload,
            context=context,
        )


class ApiServerError(ApiError):
    """Adapter error for server-side HTTP failures (5xx)."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        payload: Any = None,
        context: Optional[str] = None,
    ) -> None:
        """Initialize a 5xx adapter error.

        Args:
            message: Human-readable summary.
            status: HTTP status code in the 5xx range.
            payload: Parsed response payload for diagnostics.
            context: Adapter context string identifying the failing operation.
        """
        super().__init__(
            message,
            status=status,
            payload=payload,
            context=context,
        )


class ApiTimeoutError(ApiError):
    """Adapter error for timeout/connectivity failures before HTTP response."""

    def __init__(
        self,
        message: str,
        *,
        context: Optional[str] = None,
    ) -> None:
        """Initialize a transport timeout error.

        Args:
            message: Human-readable summary.
            context: Adapter context string identifying the failing operation.
        """
        super().__init__(message, context=context)


def parse_error_payload(resp: Any) -> Any:
    """Parse an error payload without raising parsing exceptions.

    Args:
        resp: Response-like object with ``json()`` and optional ``text``.

    Returns:
        Parsed JSON payload, truncated text snippet, or ``None``.
    """
    try:
        return resp.json()
    except Exception:
        snippet = getattr(resp, "text", "")
        if not snippet:
            return None
        return snippet[:400]


def build_error_message(ctx: str, status: int, payload: Any) -> str:
    """Build a user-facing message from error context and payload details.

    Args:
        ctx: Adapter context string (operation name and box/run scope).
        status: HTTP status code.
        payload: Parsed payload or text snippet from the response.

    Returns:
        Display-ready message used for adapter exceptions.
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
    """Extract backend error code from payload dictionaries.

    Args:
        payload: Parsed response payload.

    Returns:
        Error code text if available, otherwise ``None``.
    """
    if isinstance(payload, dict):
        value = payload.get("code") or payload.get("error_code")
        if value is None:
            return None
        return value if isinstance(value, str) else str(value)
    return None


def extract_error_hint(payload: Any) -> Optional[str]:
    """Extract user-facing hint text from dynamic payload shapes.

    Args:
        payload: Parsed response payload.

    Returns:
        Hint text if available, otherwise ``None``.
    """
    if isinstance(payload, dict):
        value = payload.get("hint") or payload.get("details") or payload.get("message")
        return _payload_detail(value)
    if isinstance(payload, str):
        return payload.strip() or None
    return None


def _payload_detail(payload: Any) -> Optional[str]:
    """Extract detail text from strings or common dictionary keys.

    Args:
        payload: Parsed payload value.

    Returns:
        Best available detail text, or ``None``.
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
