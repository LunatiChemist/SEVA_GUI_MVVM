"""Typed domain objects for remote update workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


UpdateState = Literal["queued", "running", "done", "failed", "partial"]
UpdateAction = Literal["updated", "skipped", "staged", "failed"]
UpdateStepState = Literal["pending", "running", "done", "skipped", "failed"]


@dataclass(frozen=True)
class UpdateStartResult:
    """Start response from `/updates` for one target box."""

    update_id: str
    status: UpdateState


@dataclass(frozen=True)
class UpdateStep:
    """One pipeline step status in update polling responses."""

    step: str
    status: UpdateStepState
    message: str = ""


@dataclass(frozen=True)
class UpdateComponentResult:
    """One component action outcome in update polling responses."""

    component: str
    action: UpdateAction
    from_version: str = "unknown"
    to_version: str = "unknown"
    message: str = ""
    error_code: str = ""


@dataclass(frozen=True)
class UpdateStatus:
    """Remote update status payload normalized by adapters."""

    update_id: str
    status: UpdateState
    started_at: str = ""
    finished_at: str = ""
    bundle_version: str = ""
    steps: Tuple[UpdateStep, ...] = ()
    component_results: Tuple[UpdateComponentResult, ...] = ()

    @property
    def is_terminal(self) -> bool:
        """Return whether update status reached a terminal state."""
        return self.status in {"done", "failed", "partial"}


@dataclass(frozen=True)
class BoxVersionInfo:
    """Version payload normalized from `/version` endpoint."""

    api: str = "unknown"
    pybeep: str = "unknown"
    python: str = "unknown"
    build: str = "unknown"
    firmware_staged_version: str = "unknown"
    firmware_device_version: str = "unknown"

