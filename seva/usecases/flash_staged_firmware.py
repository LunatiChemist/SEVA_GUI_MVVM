"""Use case for flashing staged firmware across multiple boxes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable

from seva.domain.ports import BoxId, FirmwarePort, UseCaseError


@dataclass
class FlashStagedFirmwareResult:
    """Structured result for staged firmware flash attempts."""

    successes: Dict[BoxId, Dict[str, Any]] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)


@dataclass
class FlashStagedFirmware:
    """Trigger staged firmware flashing per selected box."""

    firmware_port: FirmwarePort

    def __call__(self, *, box_ids: Iterable[BoxId]) -> FlashStagedFirmwareResult:
        """Flash staged firmware for all requested boxes."""
        boxes = [str(box_id) for box_id in box_ids if str(box_id).strip()]
        if not boxes:
            raise UseCaseError("FIRMWARE_NO_TARGETS", "No target boxes configured.")

        result = FlashStagedFirmwareResult()
        for box_id in boxes:
            try:
                response = self.firmware_port.flash_staged_firmware(box_id)
            except Exception as exc:
                result.failures[box_id] = str(exc)
                continue
            result.successes[box_id] = dict(response or {})
        return result


__all__ = ["FlashStagedFirmware", "FlashStagedFirmwareResult"]

