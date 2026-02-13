"""Use case for starting remote package updates across selected boxes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable

from seva.domain.ports import BoxId, UpdatePort, UseCaseError
from seva.domain.remote_update import UpdateStartReceipt
from seva.usecases.error_mapping import map_api_error


@dataclass
class StartRemoteUpdateResult:
    """Per-box outcome for package update start attempts."""

    started: Dict[BoxId, UpdateStartReceipt] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)


@dataclass
class StartRemoteUpdate:
    """Use-case callable that uploads one package ZIP to selected boxes."""

    update_port: UpdatePort

    def __call__(
        self,
        *,
        box_ids: Iterable[BoxId],
        package_path: str | Path,
    ) -> StartRemoteUpdateResult:
        boxes = [str(box_id) for box_id in box_ids if str(box_id).strip()]
        if not boxes:
            raise UseCaseError("UPDATE_NO_TARGETS", "No target boxes configured.")

        path = Path(package_path).expanduser()
        if not path.exists():
            raise UseCaseError("UPDATE_PACKAGE_NOT_FOUND", f"Update package not found: {path}")
        if path.is_dir():
            raise UseCaseError("UPDATE_PACKAGE_INVALID", f"Update package path is a directory: {path}")
        if path.suffix.lower() != ".zip":
            raise UseCaseError("UPDATE_PACKAGE_INVALID", "Update package must be a .zip file.")

        result = StartRemoteUpdateResult()
        for box_id in boxes:
            try:
                receipt = self.update_port.start_package_update(box_id, path)
            except Exception as exc:
                mapped = map_api_error(
                    exc,
                    default_code="UPDATE_START_FAILED",
                    default_message="Failed to start update.",
                )
                result.failures[box_id] = mapped.message
                continue
            result.started[box_id] = receipt

        if not result.started:
            details = "; ".join(f"{box}: {msg}" for box, msg in sorted(result.failures.items()))
            message = details or "Failed to start update on all boxes."
            raise UseCaseError("UPDATE_START_FAILED", message)

        return result


__all__ = ["StartRemoteUpdate", "StartRemoteUpdateResult"]

