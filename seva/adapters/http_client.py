"""Shared HTTP session wrapper with retries and API-key header support.

REST adapters compose `RetryingSession` to centralize timeout handling and avoid
duplicating request/response plumbing logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from requests import exceptions as req_exc

from .api_errors import ApiError, ApiTimeoutError


@dataclass
class HttpConfig:
    """HTTP retry and timeout configuration shared by REST adapters.
    
    Attributes:
        Fields are consumed by adapter call sites and session helpers.
    """
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    retries: int = 2


class RetryingSession:
    """Shared requests wrapper with optional API key and simple retries."""

    def __init__(self, api_key: Optional[str], cfg: HttpConfig) -> None:
        self.session = requests.Session()
        self.api_key = api_key
        self.cfg = cfg

    def _headers(
        self, accept: str = "application/json", json_body: bool = False
    ) -> Dict[str, str]:
        headers = {"Accept": accept}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        timeout: Optional[int] = None,
        stream: bool = False,
    ) -> requests.Response:
        context = f"GET {url}"
        last_err: ApiTimeoutError | None = None
        attempts = self.cfg.retries + 1
        for _ in range(attempts):
            try:
                return self.session.get(
                    url,
                    params=params,
                    headers=self._headers(accept=accept),
                    timeout=timeout or self.cfg.request_timeout_s,
                    stream=stream,
                )
            except (req_exc.Timeout, req_exc.ConnectionError):
                last_err = ApiTimeoutError(f"Timeout contacting {url}", context=context)
        raise last_err

    def post(
        self,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        context = f"POST {url}"
        data = None if json_body is None else json.dumps(json_body)
        last_err: ApiTimeoutError | None = None
        attempts = self.cfg.retries + 1
        for _ in range(attempts):
            try:
                return self.session.post(
                    url,
                    data=data,
                    headers=self._headers(json_body=json_body is not None),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except (req_exc.Timeout, req_exc.ConnectionError):
                last_err = ApiTimeoutError(f"Timeout contacting {url}", context=context)
        raise last_err

    def post_multipart(
        self,
        url: str,
        *,
        files: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> requests.Response:
        context = f"POST {url}"
        last_err: ApiTimeoutError | None = None
        attempts = self.cfg.retries + 1
        for _ in range(attempts):
            try:
                for value in files.values():
                    handle = None
                    if hasattr(value, "seek"):
                        handle = value
                    elif isinstance(value, tuple) and len(value) >= 2:
                        candidate = value[1]
                        if hasattr(candidate, "seek"):
                            handle = candidate
                    if handle is not None:
                        try:
                            handle.seek(0)
                        except Exception:
                            pass
                return self.session.post(
                    url,
                    files=files,
                    headers=self._headers(accept="application/json"),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except (req_exc.Timeout, req_exc.ConnectionError):
                last_err = ApiTimeoutError(f"Timeout contacting {url}", context=context)
        raise last_err


__all__ = ["HttpConfig", "RetryingSession"]
