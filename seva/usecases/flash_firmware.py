"""Use case for multi-box firmware flashing.

The workflow validates firmware file inputs, executes flashing per target box,
and returns structured success/failure breakdowns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

from seva.domain.ports import BoxId, FirmwarePort, UseCaseError


@dataclass
class FlashFirmwareResult:
    """Structured result container for firmware flashing outcomes.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    successes: Dict[BoxId, Dict[str, Any]] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)


@dataclass
class FlashFirmware:
    """Use-case callable for firmware flashing per box.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    firmware_port: FirmwarePort

    def __call__(self, *, box_ids: Iterable[BoxId], firmware_path: str | Path) -> FlashFirmwareResult:
        """Flash one firmware image across selected boxes.

        Args:
            box_ids: Target box identifiers selected by the operator.
            firmware_path: Local filesystem path to the firmware image.

        Returns:
            FlashFirmwareResult: Per-box success and failure breakdown.

        Side Effects:
            Performs adapter calls for each target box and records outcomes.

        Call Chain:
            Settings firmware action -> ``FlashFirmware.__call__`` ->
            ``FirmwarePort.flash_firmware``.

        Usage:
            Batch-updates firmware while preserving partial success details.

        Raises:
            UseCaseError: If no targets are provided or the firmware path is
                invalid.
        """
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
