"""Domain DTOs for per-box version refresh results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class BoxVersionInfo:
    """Typed version and health snapshot for one configured box."""

    configured_box_id: str
    api_version: str
    pybeep_version: str
    firmware_version: str
    python_version: str
    build_identifier: str
    health_ok: Optional[bool]
    health_devices: Optional[int]
    reported_box_id: Optional[str]

    @classmethod
    def from_payloads(
        cls,
        *,
        configured_box_id: str,
        version_payload: Mapping[str, Any],
        health_payload: Mapping[str, Any],
    ) -> "BoxVersionInfo":
        """Build typed box version info from raw adapter payloads."""
        box_key = str(configured_box_id or "").strip()
        if not box_key:
            raise ValueError("configured_box_id must be non-empty")

        def _as_text(payload: Mapping[str, Any], key: str) -> str:
            value = payload.get(key)
            return str(value).strip() if value is not None else ""

        def _as_bool(payload: Mapping[str, Any], key: str) -> Optional[bool]:
            value = payload.get(key)
            if value is None:
                return None
            return bool(value)

        def _as_int(payload: Mapping[str, Any], key: str) -> Optional[int]:
            value = payload.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        reported_box_id_raw = health_payload.get("box_id")
        reported_box_id = (
            str(reported_box_id_raw).strip() if reported_box_id_raw is not None else None
        )
        if reported_box_id == "":
            reported_box_id = None

        return cls(
            configured_box_id=box_key,
            api_version=_as_text(version_payload, "api"),
            pybeep_version=_as_text(version_payload, "pybeep"),
            firmware_version=_as_text(version_payload, "firmware"),
            python_version=_as_text(version_payload, "python"),
            build_identifier=_as_text(version_payload, "build"),
            health_ok=_as_bool(health_payload, "ok"),
            health_devices=_as_int(health_payload, "devices"),
            reported_box_id=reported_box_id,
        )


__all__ = ["BoxVersionInfo"]
