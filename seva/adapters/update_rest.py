"""REST adapter implementing remote update transport contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import requests

from seva.domain.ports import BoxId, UpdatePort
from seva.domain.update_models import (
    BoxVersionInfo,
    UpdateComponentResult,
    UpdateStartResult,
    UpdateStatus,
    UpdateStep,
)

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


_UPDATE_STATES = {"queued", "running", "done", "failed", "partial"}
_UPDATE_STEP_STATES = {"pending", "running", "done", "skipped", "failed"}
_UPDATE_ACTIONS = {"updated", "skipped", "staged", "failed"}


class UpdateRestAdapter(UpdatePort):
    """HTTP adapter for `/updates*` and `/version` endpoints."""

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

    def start_update(self, box_id: BoxId, zip_path: str | Path) -> UpdateStartResult:
        """Upload one update ZIP to `/updates`."""
        path = Path(zip_path)
        url = self._make_url(box_id, "/updates")
        session = self._session(box_id)
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "application/zip")}
            resp = session.post_multipart(url, files=files, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"start_update[{box_id}]")
        return self._parse_start_result(self._json_dict(resp))

    def get_update_status(self, box_id: BoxId, update_id: str) -> UpdateStatus:
        """Poll update status from `/updates/{update_id}`."""
        normalized_id = str(update_id or "").strip()
        if not normalized_id:
            raise ValueError("update_id is required")
        url = self._make_url(box_id, f"/updates/{normalized_id}")
        resp = self._session(box_id).get(url, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"get_update_status[{box_id}]")
        return self._parse_update_status(self._json_dict(resp))

    def get_version_info(self, box_id: BoxId) -> BoxVersionInfo:
        """Fetch `/version` payload for one box."""
        url = self._make_url(box_id, "/version")
        resp = self._session(box_id).get(url, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"get_version_info[{box_id}]")
        payload = self._json_dict(resp)
        return BoxVersionInfo(
            api=str(payload.get("api") or "unknown"),
            pybeep=str(payload.get("pybeep") or "unknown"),
            python=str(payload.get("python") or "unknown"),
            build=str(payload.get("build") or "unknown"),
            firmware_staged_version=str(payload.get("firmware_staged_version") or "unknown"),
            firmware_device_version=str(payload.get("firmware_device_version") or "unknown"),
        )

    # ------------------------------------------------------------------
    def _session(self, box_id: BoxId) -> RetryingSession:
        """Return configured session for one box id."""
        try:
            return self.sessions[box_id]
        except KeyError as exc:
            raise ValueError(f"No session configured for box '{box_id}'") from exc

    def _make_url(self, box_id: BoxId, path: str) -> str:
        """Build endpoint URL from box base URL and path."""
        base = self.base_urls.get(box_id)
        if not base:
            raise ValueError(f"No base URL configured for box '{box_id}'")
        if base.endswith("/"):
            base = base[:-1]
        return f"{base}{path}"

    @staticmethod
    def _ensure_ok(resp: requests.Response, ctx: str) -> None:
        """Raise typed adapter errors for non-2xx responses."""
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
    def _json_dict(resp: requests.Response) -> Dict[str, Any]:
        """Parse response JSON and require object payload."""
        try:
            payload = resp.json()
        except Exception:
            snippet = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {snippet}")
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid JSON response shape: expected object")
        return dict(payload)

    @staticmethod
    def _parse_start_result(payload: Mapping[str, Any]) -> UpdateStartResult:
        """Normalize `/updates` start response payload."""
        update_id = str(payload.get("update_id") or "").strip()
        status = str(payload.get("status") or "").strip()
        if not update_id:
            raise RuntimeError("Invalid update start payload: update_id missing")
        if status not in _UPDATE_STATES:
            raise RuntimeError("Invalid update start payload: status is invalid")
        return UpdateStartResult(update_id=update_id, status=status)

    @staticmethod
    def _parse_update_status(payload: Mapping[str, Any]) -> UpdateStatus:
        """Normalize `/updates/{id}` status payload."""
        update_id = str(payload.get("update_id") or "").strip()
        status = str(payload.get("status") or "").strip()
        if not update_id:
            raise RuntimeError("Invalid update status payload: update_id missing")
        if status not in _UPDATE_STATES:
            raise RuntimeError("Invalid update status payload: status is invalid")

        steps = []
        for raw_step in payload.get("steps") or []:
            if not isinstance(raw_step, Mapping):
                raise RuntimeError("Invalid update status payload: step entry is invalid")
            step_name = str(raw_step.get("step") or "").strip()
            step_status = str(raw_step.get("status") or "").strip()
            if not step_name:
                raise RuntimeError("Invalid update status payload: step name missing")
            if step_status not in _UPDATE_STEP_STATES:
                raise RuntimeError("Invalid update status payload: step status is invalid")
            steps.append(
                UpdateStep(
                    step=step_name,
                    status=step_status,
                    message=str(raw_step.get("message") or ""),
                )
            )

        component_results = []
        for raw_item in payload.get("component_results") or []:
            if not isinstance(raw_item, Mapping):
                raise RuntimeError("Invalid update status payload: component result is invalid")
            component = str(raw_item.get("component") or "").strip()
            action = str(raw_item.get("action") or "").strip()
            if not component:
                raise RuntimeError("Invalid update status payload: component missing")
            if action not in _UPDATE_ACTIONS:
                raise RuntimeError("Invalid update status payload: component action is invalid")
            component_results.append(
                UpdateComponentResult(
                    component=component,
                    action=action,
                    from_version=str(raw_item.get("from_version") or "unknown"),
                    to_version=str(raw_item.get("to_version") or "unknown"),
                    message=str(raw_item.get("message") or ""),
                    error_code=str(raw_item.get("error_code") or ""),
                )
            )

        return UpdateStatus(
            update_id=update_id,
            status=status,
            started_at=str(payload.get("started_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            bundle_version=str(payload.get("bundle_version") or ""),
            steps=tuple(steps),
            component_results=tuple(component_results),
        )


__all__ = ["UpdateRestAdapter"]

