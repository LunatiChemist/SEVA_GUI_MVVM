"""Use case for uploading one remote update ZIP to one box."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from seva.domain.ports import BoxId, UpdatePort, UseCaseError
from seva.domain.update_models import UpdateStartResult
from seva.usecases.error_mapping import map_api_error


@dataclass
class UploadRemoteUpdate:
    """Start remote update workflow by sending ZIP to `/updates`."""

    update_port: UpdatePort

    def __call__(self, *, box_id: BoxId, zip_path: str | Path) -> UpdateStartResult:
        """Validate zip path and start remote update for one box."""
        normalized_box = str(box_id).strip()
        if not normalized_box:
            raise UseCaseError("UPDATE_NO_TARGET", "Target box is required.")

        path = Path(zip_path).expanduser()
        if not path.exists():
            raise UseCaseError("UPDATE_BUNDLE_NOT_FOUND", f"Update bundle not found: {path}")
        if path.is_dir():
            raise UseCaseError("UPDATE_BUNDLE_INVALID", f"Update bundle path is a directory: {path}")
        if path.suffix.lower() != ".zip":
            raise UseCaseError("UPDATE_BUNDLE_INVALID", "Update bundle must be a .zip file.")

        try:
            return self.update_port.start_update(normalized_box, path)
        except UseCaseError:
            raise
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="UPDATE_UPLOAD_FAILED",
                default_message="Remote update upload failed.",
            ) from exc


__all__ = ["UploadRemoteUpdate"]

