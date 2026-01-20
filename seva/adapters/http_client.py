from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from requests import exceptions as req_exc

from .api_errors import ApiError, ApiTimeoutError


@dataclass
class HttpConfig:
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
        last_err: Optional[Exception] = None
        context = f"GET {url}"
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.get(
                    url,
                    params=params,
                    headers=self._headers(accept=accept),
                    timeout=timeout or self.cfg.request_timeout_s,
                    stream=stream,
                )
            except (req_exc.Timeout, req_exc.ConnectionError) as exc:
                last_err = ApiTimeoutError(
                    f"Timeout contacting {url}", context=context
                )
            except Exception as exc:
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
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.post(
                    url,
                    data=data,
                    headers=self._headers(json_body=json_body is not None),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except (req_exc.Timeout, req_exc.ConnectionError) as exc:
                last_err = ApiTimeoutError(
                    f"Timeout contacting {url}", context=context
                )
            except Exception as exc:
                last_err = exc
        if last_err is None:
            raise ApiError("Unexpected request failure", context=context)
        if isinstance(last_err, ApiError):
            raise last_err
        if isinstance(last_err, req_exc.RequestException):
            raise ApiError(str(last_err), context=context) from last_err
        raise last_err


__all__ = ["HttpConfig", "RetryingSession"]
