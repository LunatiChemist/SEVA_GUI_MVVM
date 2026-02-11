"""Hexagonal port interfaces and use-case level error contracts.

Adapters implement these protocols, while use cases depend on them to keep I/O
outside orchestration and view-model layers.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Protocol, Tuple

from seva.domain.entities import BoxId, ExperimentPlan, WellId

RunGroupId = str


# ---- Error model ----
class UseCaseError(Exception):
    """Base class for use case level errors (user-presentable)."""

    def __init__(self, code: str, message: str, meta: Optional[Dict[str, Any]] = None):
        """Capture a normalized user-facing error code/message pair."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.meta: Optional[Dict[str, Any]] = meta


# ---- Ports (Hexagonal boundaries) ----
class JobPort(Protocol):
    """Start/cancel/poll/download operations against the Box REST API.
    Future: LiveData could be added here.
    """

    def start_batch(
        self, plan: ExperimentPlan
    ) -> Tuple[
        RunGroupId, Dict[BoxId, List[str]]
    ]:
        """Start a batch and return `(run_group_id, run_ids_by_box)`."""
        ...

    def cancel_run(self, box_id: BoxId, run_id: str) -> None:
        """Cancel a single run on a box."""
        ...

    def cancel_runs(self, box_to_run_ids: Dict[BoxId, List[str]]) -> None:
        """Cancel multiple runs grouped by box identifier."""
        ...

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        """Cancel all runs associated with one group id."""
        ...

    def poll_group(self, run_group_id: RunGroupId) -> Dict:
        """Return a normalized polling snapshot for the specified group."""
        ...

    def download_group_zip(
        self, run_group_id: RunGroupId, target_dir: str
    ) -> str:
        """Download grouped artifacts and return the written path."""
        ...


class DevicePort(Protocol):
    """Device metadata and capability endpoints provided by the boxes."""

    def health(self, box_id: BoxId) -> Dict[str, Any]:
        """Fetch box health metadata."""
        ...

    def list_devices(self, box_id: BoxId) -> List[Dict[str, Any]]:
        """Fetch `/devices` information for hardware mapping."""
        ...

    def list_device_status(self, box_id: BoxId) -> List[Dict[str, Any]]:
        """Fetch `/devices/status` for channel activity views."""
        ...

    def get_modes(self, box_id: BoxId) -> List[str]:
        """Fetch supported backend mode tokens for a box."""
        ...

    def get_mode_schema(self, box_id: BoxId, mode: str) -> Dict[str, Any]:
        """Fetch parameter schema metadata for a specific mode."""
        ...


class RelayPort(Protocol):
    """Relay operations for hardware connectivity checks and configuration."""

    def test(self, ip: str, port: int) -> bool:
        """Test whether the relay endpoint is reachable."""
        ...

    def set_electrode_mode(self, mode: Literal["2E", "3E"]) -> None:
        """Switch relay wiring mode."""
        ...


class StoragePort(Protocol):
    """Persistence for layouts and user preferences."""

    def save_layout(self, name: str, payload: Dict) -> Path:
        """Persist one named plate layout and return the written path."""
        ...

    def load_layout(self, name: str | Path) -> Dict:
        """Load one saved plate layout payload."""
        ...

    def save_user_settings(self, payload: Dict) -> None:
        """Persist user settings payload."""
        ...

    def load_user_settings(self) -> Optional[Dict]:
        """Load user settings payload if available."""
        ...


class StreamPort(Protocol):
    """Placeholder for SSE/WebSocket streaming (not implemented yet)."""

    def subscribe(self, run_group_id: RunGroupId):
        """Subscribe to live stream updates for a run group."""
        ...


class FirmwarePort(Protocol):
    """Firmware flashing operations exposed by the boxes."""

    def flash_firmware(self, box_id: BoxId, firmware_path: str | Path) -> Dict[str, Any]:
        """Upload and flash firmware on the selected box."""
        ...
