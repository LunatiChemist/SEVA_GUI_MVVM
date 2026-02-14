"""Use case for polling remote package-update status across boxes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping

from seva.domain.ports import BoxId, UpdatePort
from seva.domain.remote_update import UpdateSnapshot, UpdateStartReceipt
from seva.usecases.error_mapping import map_api_error


@dataclass
class PollRemoteUpdateResult:
    """Per-box poll snapshot and polling failures."""

    statuses: Dict[BoxId, UpdateSnapshot] = field(default_factory=dict)
    failures: Dict[BoxId, str] = field(default_factory=dict)

    def all_terminal_for(self, started: Mapping[BoxId, UpdateStartReceipt]) -> bool:
        """Return whether all started boxes are terminal (or failed to poll)."""
        expected = [str(box) for box in started.keys() if str(box).strip()]
        if not expected:
            return True
        for box in expected:
            if box in self.failures:
                continue
            snapshot = self.statuses.get(box)
            if snapshot is None or not snapshot.is_terminal:
                return False
        return True


@dataclass
class PollRemoteUpdate:
    """Use-case callable for status polling of asynchronous package updates."""

    update_port: UpdatePort

    def __call__(
        self,
        *,
        started: Mapping[BoxId, UpdateStartReceipt],
    ) -> PollRemoteUpdateResult:
        result = PollRemoteUpdateResult()
        for box_id, receipt in (started or {}).items():
            box = str(box_id or "").strip()
            if not box:
                continue
            try:
                snapshot = self.update_port.get_package_update(box, receipt.update_id)
            except Exception as exc:
                mapped = map_api_error(
                    exc,
                    default_code="UPDATE_POLL_FAILED",
                    default_message="Failed to poll update status.",
                )
                result.failures[box] = mapped.message
                continue
            result.statuses[box] = snapshot
        return result


__all__ = ["PollRemoteUpdate", "PollRemoteUpdateResult"]

