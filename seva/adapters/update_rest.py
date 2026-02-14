"""REST adapter implementing ``UpdatePort`` for remote package updates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import requests

from seva.domain.ports import BoxId, UpdatePort
from seva.domain.remote_update import UpdateSnapshot, UpdateStartReceipt

from seva.adapters.api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    build_error_message,
    extract_error_code,
    extract_error_hint,
    parse_error_payload,
)
from seva.adapters.http_client import HttpConfig, RetryingSession


class UpdateRestAdapter(UpdatePort):
    """Transport implementation for package update endpoints."""

    def __init__(
        self,
        base_urls: Dict[BoxId, str],
        *,
        api_keys: Optional[Dict[BoxId, str]] = None,
        request_timeout_s: int = 10,
        retries: int = 2,
    ) -> None:
        if not base_urls:
            raise ValueError("UpdateRestAdapter requires at least one box URL")
        self.base_urls = dict(base_urls)
        self.api_keys = dict(api_keys or {})
        self.cfg = HttpConfig(request_timeout_s=request_timeout_s, retries=retries)
        self.sessions: Dict[BoxId, RetryingSession] = {
            box: RetryingSession(self.api_keys.get(box), self.cfg)
            for box in self.base_urls
        }

    def start_package_update(self, box_id: BoxId, package_path: str | Path) -> UpdateStartReceipt:
        """Upload update package ZIP for one box."""
        path = Path(package_path).expanduser()
        url = self._make_url(box_id, "/updates/package")
        session = self._session(box_id)
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "application/zip")}
            resp = session.post_multipart(
                url,
                files=files,
                timeout=self.cfg.request_timeout_s,
            )
        self._ensure_ok(resp, f"start_package_update[{box_id}]")
        payload = self._json_object(resp)
        return UpdateStartReceipt.from_payload(payload)

    def get_package_update(self, box_id: BoxId, update_id: str) -> UpdateSnapshot:
        """Fetch status snapshot for one update job id."""
        update_key = str(update_id or "").strip()
        if not update_key:
            raise ValueError("update_id must be a non-empty string")
        url = self._make_url(box_id, f"/updates/{update_key}")
        resp = self._session(box_id).get(url, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"get_package_update[{box_id}:{update_key}]")
        payload = self._json_object(resp)
        return UpdateSnapshot.from_payload(payload)

    # ------------------------------------------------------------------
    def _session(self, box_id: BoxId) -> RetryingSession:
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
    def _json_object(resp: requests.Response) -> Dict[str, Any]:
        try:
            payload = resp.json()
        except Exception:
            snippet = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {snippet}")
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid JSON response: expected object")
        return payload


__all__ = ["UpdateRestAdapter"]

