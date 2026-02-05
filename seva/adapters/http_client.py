"""Shared HTTP transport utilities for REST adapters.

This module provides a thin wrapper around ``requests.Session`` so adapter
implementations can share timeout policy, retry behavior, and API-key header
construction.

Dependencies:
    - ``requests`` for network I/O.
    - ``seva.adapters.api_errors.ApiTimeoutError`` for typed transport failures.

Call context:
    - Constructed by REST adapters in ``seva/adapters/device_rest.py``,
      ``seva/adapters/job_rest.py``, and ``seva/adapters/firmware_rest.py``.
    - Used only inside adapter layer methods; use cases interact through ports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from requests import exceptions as req_exc

from seva.adapters.api_errors import ApiTimeoutError


@dataclass
class HttpConfig:
    """Timeout and retry configuration for adapter HTTP calls.

    Attributes:
        request_timeout_s: Default timeout in seconds for JSON API calls.
        download_timeout_s: Default timeout in seconds for artifact downloads.
        retries: Number of retry attempts after the initial request.
    """
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    retries: int = 2


class RetryingSession:
    """Shared requests wrapper with API-key headers and retry loops.

    This class is intentionally transport-only. Callers provide endpoint URLs and
    decide how to map non-2xx responses into domain/use-case errors.
    """

    def __init__(self, api_key: Optional[str], cfg: HttpConfig) -> None:
        """Create a retry-enabled session.

        Args:
            api_key: API key value to place in ``X-API-Key`` headers, or ``None``.
            cfg: Shared timeout and retry settings.

        Side Effects:
            Creates a persistent ``requests.Session`` object.
        """
        self.session = requests.Session()
        self.api_key = api_key
        self.cfg = cfg

    def _headers(
        self, accept: str = "application/json", json_body: bool = False
    ) -> Dict[str, str]:
        """Build request headers for adapter calls.

        Args:
            accept: ``Accept`` header value expected by the caller.
            json_body: Whether to add ``Content-Type: application/json``.

        Returns:
            Dictionary of request headers.
        """
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
        """Send a GET request with retries on timeout/connectivity failures.

        Args:
            url: Absolute endpoint URL.
            params: Optional query parameter mapping.
            accept: ``Accept`` header value.
            timeout: Optional timeout override in seconds.
            stream: Whether to stream the response body.

        Returns:
            ``requests.Response`` from the first successful attempt.

        Raises:
            ApiTimeoutError: If all attempts fail with timeout/connection errors.

        Call Chain:
            Adapter methods -> ``RetryingSession.get`` -> ``requests.Session.get``.
        """
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
        """Send a JSON POST request with retries on transport failures.

        Args:
            url: Absolute endpoint URL.
            json_body: Optional payload object serialized to JSON text.
            timeout: Optional timeout override in seconds.

        Returns:
            ``requests.Response`` from the first successful attempt.

        Raises:
            ApiTimeoutError: If all attempts fail with timeout/connection errors.

        Side Effects:
            Serializes ``json_body`` with ``json.dumps`` before sending.
        """
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
        """Send a multipart POST request with retry-safe file handle rewinds.

        Args:
            url: Absolute endpoint URL.
            files: Multipart mapping consumed by ``requests``.
            timeout: Optional timeout override in seconds.

        Returns:
            ``requests.Response`` from the first successful attempt.

        Raises:
            ApiTimeoutError: If all attempts fail with timeout/connection errors.

        Side Effects:
            Seeks file handles to offset ``0`` before each retry to avoid partial
            uploads after failed attempts.
        """
        context = f"POST {url}"
        last_err: ApiTimeoutError | None = None
        attempts = self.cfg.retries + 1
        for _ in range(attempts):
            try:
                # Multipart retries must rewind file handles so each attempt sends
                # the full file payload from the beginning.
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
