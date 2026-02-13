"""Domain DTOs for remote package update workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


TERMINAL_UPDATE_STATES = {"done", "failed"}


@dataclass(frozen=True)
class UpdateStartReceipt:
    """Typed response returned when a package update is queued."""

    update_id: str
    status: str
    step: str
    queued_at: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "UpdateStartReceipt":
        """Build typed receipt from adapter payload."""
        update_id = str(payload.get("update_id") or "").strip()
        if not update_id:
            raise ValueError("Missing update_id in start response.")
        status = str(payload.get("status") or "queued").strip().lower() or "queued"
        step = str(payload.get("step") or "queued").strip() or "queued"
        queued_at_raw = payload.get("queued_at") or payload.get("created_at")
        queued_at = str(queued_at_raw).strip() if queued_at_raw else None
        return cls(
            update_id=update_id,
            status=status,
            step=step,
            queued_at=queued_at,
        )


@dataclass(frozen=True)
class UpdateSnapshot:
    """Typed status snapshot for one asynchronous package update."""

    update_id: str
    status: str
    step: str
    message: str
    heartbeat_at: Optional[str]
    observed_at: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    components: Dict[str, str] = field(default_factory=dict)
    restart: Dict[str, Any] = field(default_factory=dict)
    error: Dict[str, str] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Return whether update has reached a terminal state."""
        return self.status in TERMINAL_UPDATE_STATES

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "UpdateSnapshot":
        """Build typed snapshot from adapter payload."""
        update_id = str(payload.get("update_id") or "").strip()
        if not update_id:
            raise ValueError("Missing update_id in status response.")
        status = str(payload.get("status") or "queued").strip().lower() or "queued"
        step = str(payload.get("step") or "queued").strip() or "queued"
        message = str(payload.get("message") or "").strip()

        def _as_text(value: Any) -> Optional[str]:
            text = str(value).strip() if value is not None else ""
            return text or None

        components_raw = payload.get("components") if isinstance(payload.get("components"), Mapping) else {}
        restart_raw = payload.get("restart") if isinstance(payload.get("restart"), Mapping) else {}
        error_raw = payload.get("error") if isinstance(payload.get("error"), Mapping) else {}
        components = {str(k): str(v) for k, v in components_raw.items()}
        restart = {str(k): v for k, v in restart_raw.items()}
        error = {str(k): str(v) for k, v in error_raw.items()}

        return cls(
            update_id=update_id,
            status=status,
            step=step,
            message=message,
            heartbeat_at=_as_text(payload.get("heartbeat_at")),
            observed_at=_as_text(payload.get("observed_at")),
            started_at=_as_text(payload.get("started_at")),
            ended_at=_as_text(payload.get("ended_at")),
            components=components,
            restart=restart,
            error=error,
        )


__all__ = ["UpdateStartReceipt", "UpdateSnapshot", "TERMINAL_UPDATE_STATES"]

