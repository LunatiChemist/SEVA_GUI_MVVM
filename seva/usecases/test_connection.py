"""Use case for connectivity checks against one box.

It gathers health and device lists through `DevicePort` and returns a structured
result payload for settings and diagnostics screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from seva.domain.ports import BoxId, DevicePort, UseCaseError
from seva.usecases.error_mapping import map_api_error


@dataclass
class TestConnection:
    """Use-case callable for device connection diagnostics.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    device_port: DevicePort

    def __call__(self, box_id: BoxId) -> Dict[str, Any]:
        """Probe one box and summarize health/device diagnostics for the UI.

        Args:
            box_id: Box identifier selected in settings.

        Returns:
            Dict[str, Any]: Structured diagnostic payload with health and devices.

        Side Effects:
            Performs two adapter calls: ``health`` and ``list_devices``.

        Call Chain:
            Settings test action -> ``TestConnection.__call__`` -> ``DevicePort``.

        Usage:
            Supports immediate connectivity checks before run submission.

        Raises:
            UseCaseError: Adapter and transport errors mapped via
                ``map_api_error``.
        """
        try:
            health = self.device_port.health(box_id)
            devices = self.device_port.list_devices(box_id)
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="TEST_CONNECTION_FAILED",
                default_message="Connection test failed.",
            ) from exc

        health_map = dict(health or {})
        device_list: List[Dict[str, Any]] = list(devices or [])

        ok_flag = bool(health_map.get("ok", True))
        device_count = len(device_list)
        health_map.setdefault("devices", device_count)

        return {
            "box_id": box_id,
            "ok": ok_flag,
            "health": health_map,
            "devices": device_list,
            "device_count": device_count,
        }
