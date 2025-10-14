from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from seva.domain.ports import BoxId, DevicePort, UseCaseError


@dataclass
class TestConnection:
    device_port: DevicePort

    def __call__(self, box_id: BoxId) -> Dict[str, Any]:
        try:
            health = self.device_port.health(box_id)
            devices = self.device_port.list_devices(box_id)
        except Exception as exc:
            raise UseCaseError("TEST_CONNECTION_FAILED", str(exc))

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
