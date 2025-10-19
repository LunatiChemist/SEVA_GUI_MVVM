from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Protocol, Tuple

WellId = str
BoxId = str
RunGroupId = str


# ---- Error model ----
class UseCaseError(Exception):
    """Base class for use case level errors (user-presentable)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---- Ports (Hexagonal boundaries) ----
class JobPort(Protocol):
    """Start/cancel/poll/download operations against the Box REST API.
    Future: LiveData could be added here.
    """

    def start_batch(
        self, plan: Dict
    ) -> Tuple[
        RunGroupId, Dict[BoxId, List[str]]
    ]: ...  # returns run_group_id, subrun per box
    def cancel_run(self, box_id: BoxId, run_id: str) -> None: ...
    def cancel_runs(self, box_to_run_ids: Dict[BoxId, List[str]]) -> None: ...
    def cancel_group(self, run_group_id: RunGroupId) -> None: ...
    def poll_group(self, run_group_id: RunGroupId) -> Dict: ...  # normalized snapshot
    def download_group_zip(
        self, run_group_id: RunGroupId, target_dir: str
    ) -> str: ...  # returns path


class DevicePort(Protocol):
    """Device metadata and capability endpoints provided by the boxes."""

    def health(self, box_id: BoxId) -> Dict[str, Any]: ...
    def list_devices(self, box_id: BoxId) -> List[Dict[str, Any]]: ...
    def list_modes(self, box_id: BoxId) -> List[Dict[str, Any]]: ...
    def get_mode_params(self, box_id: BoxId, mode: str) -> Dict[str, Any]: ...
    def validate_mode(
        self, box_id: BoxId, mode: str, params: Dict[str, Any]
    ) -> Dict[str, Any]: ...


class RelayPort(Protocol):
    """Relay operations for hardware connectivity checks and configuration."""

    def test(self, ip: str, port: int) -> bool: ...
    def set_electrode_mode(self, mode: Literal["2E", "3E"]) -> None: ...


class StoragePort(Protocol):
    """Persistence for layouts and user preferences."""

    def save_layout(self, name: str, payload: Dict) -> Path: ...
    def load_layout(self, name: str | Path) -> Dict: ...
    def save_user_settings(self, payload: Dict) -> None: ...
    def load_user_settings(self) -> Optional[Dict]: ...


class StreamPort(Protocol):
    """Placeholder for SSE/WebSocket streaming (not implemented yet)."""

    def subscribe(self, run_group_id: RunGroupId): ...
