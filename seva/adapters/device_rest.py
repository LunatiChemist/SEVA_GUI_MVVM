from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from requests import exceptions as req_exc

from seva.domain.ports import BoxId, DevicePort

from .api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    ApiTimeoutError,
    build_error_message,
    extract_error_code,
    extract_error_hint,
    parse_error_payload,
)


@dataclass
class _HttpConfig:
    request_timeout_s: int = 10
    retries: int = 2


class _RetryingSession:
    """Minified requests wrapper with optional API key and simple retries."""

    def __init__(self, api_key: Optional[str], cfg: _HttpConfig) -> None:
        self.session = requests.Session()
        self.api_key = api_key
        self.cfg = cfg

    def _headers(self, *, accept: str = "application/json") -> Dict[str, str]:
        headers = {"Accept": accept}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def get(
        self,
        url: str,
        *,
        timeout: Optional[int] = None,
        accept: str = "application/json",
    ) -> requests.Response:
        last_err: Optional[Exception] = None
        context = f"GET {url}"
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.get(
                    url,
                    headers=self._headers(accept=accept),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except Exception as exc:
                if isinstance(exc, (req_exc.Timeout, req_exc.ConnectionError)):
                    last_err = ApiTimeoutError(f"Timeout contacting {url}", context=context)
                else:
                    last_err = exc
        if last_err is None:
            raise ApiError("Unexpected request failure", context=context)
        if isinstance(last_err, ApiError):
            raise last_err
        if isinstance(last_err, req_exc.RequestException):
            raise ApiError(str(last_err), context=context) from last_err
        raise last_err

    def post(
        self,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        last_err: Optional[Exception] = None
        context = f"POST {url}"
        data = None if json_body is None else json.dumps(json_body)
        headers = self._headers(accept="application/json")
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.post(
                    url,
                    data=data,
                    headers=headers,
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except Exception as exc:
                if isinstance(exc, (req_exc.Timeout, req_exc.ConnectionError)):
                    last_err = ApiTimeoutError(f"Timeout contacting {url}", context=context)
                else:
                    last_err = exc
        if last_err is None:
            raise ApiError("Unexpected request failure", context=context)
        if isinstance(last_err, ApiError):
            raise last_err
        if isinstance(last_err, req_exc.RequestException):
            raise ApiError(str(last_err), context=context) from last_err
        raise last_err


class DeviceRestAdapter(DevicePort):
    """REST adapter that exposes device and capability metadata endpoints."""

    def __init__(
        self,
        base_urls: Dict[BoxId, str],
        *,
        api_keys: Optional[Dict[BoxId, str]] = None,
        request_timeout_s: int = 10,
        retries: int = 2,
    ) -> None:
        if not base_urls:
            raise ValueError("DeviceRestAdapter requires at least one box URL")

        self.base_urls = dict(base_urls)
        self.api_keys = dict(api_keys or {})
        self.cfg = _HttpConfig(request_timeout_s=request_timeout_s, retries=retries)
        self.sessions: Dict[BoxId, _RetryingSession] = {
            box: _RetryingSession(self.api_keys.get(box), self.cfg)
            for box in self.base_urls
        }

    def health(self, box_id: BoxId) -> Dict[str, Any]:
        url = self._make_url(box_id, "/health")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"health[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(f"health[{box_id}]: expected object response")
        return data

    def list_devices(self, box_id: BoxId) -> List[Dict[str, Any]]:
        url = self._make_url(box_id, "/devices")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"devices[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, list):
            raise RuntimeError(f"devices[{box_id}]: expected list response")
        return [entry for entry in data if isinstance(entry, dict)]

    def list_modes(self, box_id: BoxId) -> List[Dict[str, Any]]:
        url = self._make_url(box_id, "/modes")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"modes[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, list):
            raise RuntimeError(f"modes[{box_id}]: expected list response")

        cleaned: List[Dict[str, Any]] = []
        for entry in data:
            if isinstance(entry, dict):
                cleaned.append(entry)
            elif isinstance(entry, str):
                cleaned.append({"mode": entry})
        return cleaned

    def get_mode_params(self, box_id: BoxId, mode: str) -> Dict[str, Any]:
        if not mode:
            raise ValueError("get_mode_params requires 'mode'")
        url = self._make_url(box_id, f"/modes/{mode}/params")
        resp = self._session(box_id).get(url)
        self._ensure_ok(resp, f"mode_params[{box_id}:{mode}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(
                f"mode_params[{box_id}:{mode}]: expected object response"
            )
        return data

    def validate_mode(
        self, box_id: BoxId, mode: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not mode:
            raise ValueError("validate_mode requires 'mode'")
        url = self._make_url(box_id, f"/modes/{mode}/validate")
        resp = self._session(box_id).post(url, json_body=dict(params or {}))
        self._ensure_ok(resp, f"mode_validate[{box_id}:{mode}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(
                f"mode_validate[{box_id}:{mode}]: expected object response"
            )
        return data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _session(self, box_id: BoxId) -> _RetryingSession:
        try:
            return self.sessions[box_id]
        except KeyError as exc:
            raise ValueError(f"No session configured for box '{box_id}'") from exc

    def _make_url(self, box_id: BoxId, path: str) -> str:
        base = self.base_urls.get(box_id)
        if not base:
            raise ValueError(f"No base URL configured for box '{box_id}'")
        if base.endswith("/"):
            base = base[:-1]
        return f"{base}{path}"

    @staticmethod
    def _ensure_ok(resp: requests.Response, ctx: str) -> None:
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
        try:
            return resp.json()
        except Exception:
            snippet = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {snippet}")
