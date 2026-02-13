"""Use case for reading per-box version metadata."""

from __future__ import annotations

from dataclasses import dataclass

from seva.domain.ports import BoxId, UpdatePort, UseCaseError
from seva.domain.update_models import BoxVersionInfo
from seva.usecases.error_mapping import map_api_error


@dataclass
class FetchBoxVersionInfo:
    """Fetch normalized `/version` payload through ``UpdatePort``."""

    update_port: UpdatePort

    def __call__(self, *, box_id: BoxId) -> BoxVersionInfo:
        """Return typed version payload for one configured box."""
        normalized_box = str(box_id).strip()
        if not normalized_box:
            raise UseCaseError("VERSION_NO_TARGET", "Target box is required.")
        try:
            return self.update_port.get_version_info(normalized_box)
        except UseCaseError:
            raise
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="VERSION_FETCH_FAILED",
                default_message="Version lookup failed.",
            ) from exc


__all__ = ["FetchBoxVersionInfo"]

