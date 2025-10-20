from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, List

@dataclass(frozen=True)
class DiscoveredBox:
    """Lightweight descriptor for a discovered SEVA box."""
    base_url: str                 # e.g. "http://192.168.0.42:8000"
    api_version: Optional[str] = None
    build: Optional[str] = None
    box_id: Optional[str] = None  # comes from /health
    devices: Optional[int] = None # comes from /health

class DeviceDiscoveryPort(Protocol):
    """Port for discovering SEVA devices on the network."""
    def discover(
        self,
        candidates: Sequence[str],
        api_key: Optional[str] = None,
        timeout_s: float = 0.3
    ) -> List[DiscoveredBox]:
        ...