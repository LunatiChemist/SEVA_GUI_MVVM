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
    detail = first_string(payload)
    if detail:
        return f"{ctx}: {detail} (HTTP {status})"
    return f"{ctx}: HTTP {status}"


def extract_error_code(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("code", "error", "error_code"):
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                return value
            return str(value)
    return None


def extract_error_hint(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("hint", "details", "errors", "messages"):
            if key not in payload:
                continue
            text = stringify(payload[key])
            if text:
                return text
    if isinstance(payload, list):
        return stringify(payload)
    if isinstance(payload, str):
        return payload.strip() or None
    return None


def first_string(payload: Any) -> Optional[str]:
    if isinstance(payload, str):
        text = payload.strip()
        return text or None
    if isinstance(payload, dict):
        for key in ("detail", "message", "error", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                candidate = first_string(value)
                if candidate:
                    return candidate
            if isinstance(value, dict):
                candidate = first_string(value)
                if candidate:
                    return candidate
    if isinstance(payload, list):
        for item in payload:
            candidate = first_string(item)
            if candidate:
                return candidate
    return None


def stringify(data: Any, *, limit: int = 200) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, str):
        cleaned = data.strip()
        return cleaned[:limit] if cleaned else None
    if isinstance(data, list):
        parts = []
        for item in data:
            text = stringify(item, limit=limit)
            if text:
                parts.append(text)
            if len(parts) >= 3:
                break
        if not parts:
            return None
        joined = "; ".join(parts)
        return joined[:limit]
    if isinstance(data, dict):
        pairs = []
        for key, value in list(data.items())[:4]:
            value_text = stringify(value, limit=limit)
            if value_text:
                pairs.append(f"{key}={value_text}")
        if not pairs:
            return None
        joined = ", ".join(pairs)
        return joined[:limit]
    text = str(data).strip()
    return text[:limit] if text else None
