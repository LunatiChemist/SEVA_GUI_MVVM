from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

from seva.domain.ports import BoxId, FirmwarePort, UseCaseError


@dataclass
class FlashFirmwareResult:
    successes: Dict[BoxId, Dict[str, Any]] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)


@dataclass
class FlashFirmware:
    firmware_port: FirmwarePort

    def __call__(self, *, box_ids: Iterable[BoxId], firmware_path: str | Path) -> FlashFirmwareResult:
        boxes = [str(box_id) for box_id in box_ids if str(box_id).strip()]
        if not boxes:
            raise UseCaseError("FIRMWARE_NO_TARGETS", "No target boxes configured.")

        path = Path(firmware_path).expanduser()
        if not path.exists():
            raise UseCaseError("FIRMWARE_NOT_FOUND", f"Firmware file not found: {path}")
        if path.is_dir():
            raise UseCaseError("FIRMWARE_INVALID", f"Firmware path is a directory: {path}")

        result = FlashFirmwareResult()
        for box_id in boxes:
            try:
                response = self.firmware_port.flash_firmware(box_id, path)
            except Exception as exc:
                result.failures[box_id] = str(exc)
                continue
            result.successes[box_id] = dict(response or {})

        return result


__all__ = ["FlashFirmware", "FlashFirmwareResult"]
