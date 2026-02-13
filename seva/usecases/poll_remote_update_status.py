"""Use case for polling remote update status from one box."""

from __future__ import annotations

from dataclasses import dataclass

from seva.domain.ports import BoxId, UpdatePort, UseCaseError
from seva.domain.update_models import UpdateStatus
from seva.usecases.error_mapping import map_api_error


@dataclass
class PollRemoteUpdateStatus:
    """Poll `/updates/{id}` and return typed update status."""

    update_port: UpdatePort

    def __call__(self, *, box_id: BoxId, update_id: str) -> UpdateStatus:
        """Fetch update status for one box/update id pair."""
        normalized_box = str(box_id).strip()
        normalized_update_id = str(update_id).strip()
        if not normalized_box:
            raise UseCaseError("UPDATE_NO_TARGET", "Target box is required.")
        if not normalized_update_id:
            raise UseCaseError("UPDATE_ID_REQUIRED", "Update ID is required.")
        try:
            return self.update_port.get_update_status(normalized_box, normalized_update_id)
        except UseCaseError:
            raise
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="UPDATE_POLL_FAILED",
                default_message="Remote update polling failed.",
            ) from exc


__all__ = ["PollRemoteUpdateStatus"]

