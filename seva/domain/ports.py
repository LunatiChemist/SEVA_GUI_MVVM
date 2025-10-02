from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

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
        RunGroupId, Dict[BoxId, str]
    ]: ...  # returns run_group_id, subrun per box
    def cancel_group(self, run_group_id: RunGroupId) -> None: ...
    def poll_group(self, run_group_id: RunGroupId) -> Dict: ...  # normalized snapshot
    def download_group_zip(
        self, run_group_id: RunGroupId, target_dir: str
    ) -> str: ...  # returns path


class DevicePort(Protocol):
    """Optional capabilities/device metadata from boxes."""

    def list_devices(self) -> List[Dict]: ...


class StoragePort(Protocol):
    """Persistence for layouts and user preferences."""

    def save_layout(self, name: str, wells: Iterable[WellId], params: Dict) -> None: ...
    def load_layout(self, name: str) -> Dict: ...
    def save_user_prefs(self, prefs: Dict) -> None: ...
    def load_user_prefs(self) -> Dict: ...


class StreamPort(Protocol):
    """Placeholder for SSE/WebSocket streaming (not implemented yet)."""

    def subscribe(self, run_group_id: RunGroupId): ...
