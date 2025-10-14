from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from seva.domain.ports import BoxId, DevicePort


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
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.get(
                    url,
                    headers=self._headers(accept=accept),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except Exception as exc:
                last_err = exc
        raise last_err  # type: ignore[misc]


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

        body = ""
        try:
            body = resp.text[:300]
        except Exception:
            pass

        if resp.status_code in (401, 403):
            raise RuntimeError(f"{ctx}: HTTP {resp.status_code} unauthorized {body}")
        raise RuntimeError(f"{ctx}: HTTP {resp.status_code} {body}")

    @staticmethod
    def _json_any(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            snippet = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {snippet}")
