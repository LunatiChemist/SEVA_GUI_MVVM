"""Use case for refreshing box version details in settings UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable

from seva.domain.box_version import BoxVersionInfo
from seva.domain.ports import BoxId, DevicePort, UseCaseError
from seva.usecases.error_mapping import map_api_error


@dataclass
class RefreshBoxVersionsResult:
    """Per-box version snapshots and refresh failures."""

    infos: Dict[BoxId, BoxVersionInfo] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)


@dataclass
class RefreshBoxVersions:
    """Use-case callable to collect `/version` and `/health` for each box."""

    device_port: DevicePort

    def __call__(self, *, box_ids: Iterable[BoxId]) -> RefreshBoxVersionsResult:
        boxes = [str(box_id) for box_id in box_ids if str(box_id).strip()]
        if not boxes:
            raise UseCaseError("VERSION_NO_TARGETS", "No target boxes configured.")

        result = RefreshBoxVersionsResult()
        for box_id in boxes:
            try:
                version_payload = self.device_port.version(box_id)
                health_payload = self.device_port.health(box_id)
                info = BoxVersionInfo.from_payloads(
                    configured_box_id=box_id,
                    version_payload=version_payload,
                    health_payload=health_payload,
                )
            except Exception as exc:
                mapped = map_api_error(
                    exc,
                    default_code="VERSION_REFRESH_FAILED",
                    default_message="Failed to refresh version details.",
                )
                result.failures[box_id] = mapped.message
                continue
            result.infos[box_id] = info
        return result


__all__ = ["RefreshBoxVersions", "RefreshBoxVersionsResult"]
