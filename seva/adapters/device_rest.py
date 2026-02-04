"""REST adapter implementing ``DevicePort``.

This adapter reads box metadata and mode capabilities from backend endpoints.

Dependencies:
    - ``RetryingSession``/``HttpConfig`` for shared HTTP policy.
    - ``api_errors`` for typed non-2xx handling.
    - Domain mapping helpers for device entry normalization.

Call context:
    - ``TestConnection`` use case for health/device diagnostics.
    - ``PollDeviceStatus`` use case for activity snapshots.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from seva.domain.mapping import extract_device_entries
from seva.domain.ports import BoxId, DevicePort

from .api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    build_error_message,
    extract_error_code,
    extract_error_hint,
    parse_error_payload,
)
from .http_client import HttpConfig, RetryingSession


class DeviceRestAdapter(DevicePort):
    """Transport implementation for device/capability metadata queries."""

    def __init__(
        self,
        base_urls: Dict[BoxId, str],
        *,
        api_keys: Optional[Dict[BoxId, str]] = None,
        request_timeout_s: int = 10,
        retries: int = 2,
    ) -> None:
        """Create adapter with per-box URLs and optional API keys.

        Args:
            base_urls: Mapping from ``BoxId`` to base URL.
            api_keys: Optional mapping from ``BoxId`` to API key.
            request_timeout_s: Default timeout for requests.
            retries: Retry count for transport failures.

        Raises:
            ValueError: If ``base_urls`` is empty.
        """
        if not base_urls:
            raise ValueError("DeviceRestAdapter requires at least one box URL")

        self.base_urls = dict(base_urls)
        self.api_keys = dict(api_keys or {})
        self.cfg = HttpConfig(request_timeout_s=request_timeout_s, retries=retries)
        self.sessions: Dict[BoxId, RetryingSession] = {
            box: RetryingSession(self.api_keys.get(box), self.cfg)
            for box in self.base_urls
        }
        self._mode_list_cache: Dict[BoxId, List[str]] = {}
        self._mode_schema_cache: Dict[BoxId, Dict[str, Dict[str, Any]]] = {}

    def health(self, box_id: BoxId) -> Dict[str, Any]:
        """Read ``/health`` payload for one box.

        Args:
            box_id: Box identifier to query.

        Returns:
            Parsed JSON object from health endpoint.

        Raises:
            ValueError: If box/session is not configured.
            ApiError: For non-2xx HTTP responses.
            RuntimeError: If response JSON shape is unexpected.
        """
        url = self._make_url(box_id, "/health")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"health[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(f"health[{box_id}]: expected object response")
        return data

    def list_devices(self, box_id: BoxId) -> List[Dict[str, Any]]:
        """Read and normalize ``/devices`` payload.

        Args:
            box_id: Box identifier to query.

        Returns:
            List of normalized device-entry dictionaries.
        """
        url = self._make_url(box_id, "/devices")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"devices[{box_id}]")
        data = self._json_any(resp)
        return [dict(entry) for entry in extract_device_entries(data)]

    def list_device_status(self, box_id: BoxId) -> List[Dict[str, Any]]:
        """Read ``/devices/status`` payload.

        Args:
            box_id: Box identifier to query.

        Returns:
            List of status-entry dictionaries.

        Raises:
            RuntimeError: If response is not a JSON list.
        """
        url = self._make_url(box_id, "/devices/status")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"devices/status[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, list):
            raise RuntimeError(f"devices/status[{box_id}]: expected list response")
        return [dict(entry) for entry in data if isinstance(entry, dict)]

    def get_modes(self, box_id: BoxId) -> List[str]:
        """Read supported modes for a box with cache reuse.

        Args:
            box_id: Box identifier to query.

        Returns:
            Uppercased mode token list.

        Side Effects:
            Populates in-memory mode cache by ``box_id``.
        """
        cached = self._mode_list_cache.get(box_id)
        if cached is not None:
            return list(cached)

        url = self._make_url(box_id, "/modes")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"modes[{box_id}]")
        data = self._json_any(resp)
        modes = self._normalize_modes(data, ctx=f"modes[{box_id}]")
        self._mode_list_cache[box_id] = modes
        return list(modes)

    def get_mode_schema(self, box_id: BoxId, mode: str) -> Dict[str, Any]:
        """Read parameter schema for one mode with cache reuse.

        Args:
            box_id: Box identifier to query.
            mode: User/domain mode token.

        Returns:
            Schema dictionary returned by backend.

        Side Effects:
            Populates in-memory mode-schema cache by ``box_id`` and mode key.
        """
        mode_key = self._normalize_mode_key(mode)
        cache = self._mode_schema_cache.setdefault(box_id, {})
        if mode_key in cache:
            return dict(cache[mode_key])

        url = self._make_url(box_id, f"/modes/{mode_key}/params")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"mode_schema[{box_id}:{mode_key}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(
                f"mode_schema[{box_id}:{mode_key}]: expected object response"
            )
        schema = dict(data)
        cache[mode_key] = schema
        return dict(schema)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _session(self, box_id: BoxId) -> RetryingSession:
        """Return configured session for a box.

        Args:
            box_id: Box identifier.

        Returns:
            Session configured for the box.

        Raises:
            ValueError: If no session was configured for box.
        """
        try:
            return self.sessions[box_id]
        except KeyError as exc:
            raise ValueError(f"No session configured for box '{box_id}'") from exc

    def _make_url(self, box_id: BoxId, path: str) -> str:
        """Build endpoint URL from box base URL and path.

        Args:
            box_id: Box identifier.
            path: Endpoint path beginning with ``/``.

        Returns:
            Absolute endpoint URL.

        Raises:
            ValueError: If box base URL is missing.
        """
        base = self.base_urls.get(box_id)
        if not base:
            raise ValueError(f"No base URL configured for box '{box_id}'")
        if base.endswith("/"):
            base = base[:-1]
        return f"{base}{path}"

    @staticmethod
    def _normalize_mode_key(mode: str) -> str:
        """Normalize mode token for endpoint addressing.

        Args:
            mode: Raw mode token.

        Returns:
            Uppercased non-empty mode key.

        Raises:
            ValueError: If mode is empty after trimming.
        """
        cleaned = str(mode or "").strip()
        if not cleaned:
            raise ValueError("Mode must be a non-empty string.")
        return cleaned.upper()

    @staticmethod
    def _normalize_modes(data: Any, *, ctx: str) -> List[str]:
        """Normalize backend mode list payload.

        Args:
            data: JSON payload from backend.
            ctx: Context label for error diagnostics.

        Returns:
            Uppercased non-empty mode tokens.

        Raises:
            RuntimeError: If payload shape is invalid or empty.
        """
        if not isinstance(data, list):
            raise RuntimeError(f"{ctx}: expected list response")

        modes = [entry.strip().upper() for entry in data if isinstance(entry, str) and entry.strip()]
        if not modes:
            raise RuntimeError(f"{ctx}: no valid modes in response")
        return modes

    @staticmethod
    def _ensure_ok(resp: requests.Response, ctx: str) -> None:
        """Raise typed adapter errors for non-2xx responses.

        Args:
            resp: HTTP response.
            ctx: Context label for diagnostics.

        Raises:
            ApiClientError: For HTTP 4xx responses.
            ApiServerError: For HTTP 5xx responses.
            ApiError: For all other non-2xx responses.
        """
        if 200 <= resp.status_code < 300:
            return
        status = resp.status_code
        payload = parse_error_payload(resp)
        message = build_error_message(ctx, status, payload)
        code = extract_error_code(payload)
        hint = extract_error_hint(payload)
        if 400 <= status < 500:
            raise ApiClientError(
                message,
                status=status,
                code=code,
                hint=hint,
                payload=payload,
                context=ctx,
            )
        if 500 <= status < 600:
            raise ApiServerError(
                message,
                status=status,
                payload=payload,
                context=ctx,
            )
        raise ApiError(message, status=status, payload=payload, context=ctx)

    @staticmethod
    def _json_any(resp: requests.Response) -> Any:
        """Parse arbitrary JSON from response.

        Args:
            resp: HTTP response.

        Returns:
            Parsed JSON payload.

        Raises:
            RuntimeError: If payload is not valid JSON.
        """
        try:
            return resp.json()
        except Exception:
            snippet = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {snippet}")
