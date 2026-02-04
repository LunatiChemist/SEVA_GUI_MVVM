"""Discovery contracts used between discovery use cases and adapters.

This module defines immutable records and protocol interfaces for network
discovery. `DiscoverDevices` and `DiscoverAndAssignDevices` (use-case layer)
call `DeviceDiscoveryPort.discover`, while adapters provide the HTTP probing
implementation.
"""

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
        """Probe candidate addresses and return reachable boxes.

        Args:
            candidates: Base URLs, hosts, or CIDR inputs prepared by the use case.
            api_key: Optional API key forwarded to adapter HTTP calls.
            timeout_s: Per-probe timeout in seconds.

        Returns:
            A list of discovered boxes with optional metadata populated from
            `/version` and `/health` probes.

        Side Effects:
            Performs network I/O in adapter implementations.

        Call Chain:
            ViewModel command -> discovery use case -> DeviceDiscoveryPort adapter.

        Error Cases:
            Adapter implementations may raise typed adapter errors when probing
            fails unexpectedly.
        """
        ...
