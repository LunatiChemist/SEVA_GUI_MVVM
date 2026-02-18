"""Discovery contracts used between use cases and infrastructure adapters.

The GUI discovery workflow uses mDNS/Zeroconf to find `_myapp._tcp.local.`
services on the local LAN, then validates each candidate via HTTP `/health`.
This module contains the adapter boundary records and typed adapter error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


class DiscoveryAdapterError(Exception):
    """Raised by discovery adapters when Zeroconf browsing fails unexpectedly."""


@dataclass(frozen=True)
class DiscoveredBox:
    """Normalized discovery result consumed by use cases and controllers.

    Attributes:
        name: Human-readable service instance name (suffixed when duplicated).
        ip: IPv4 address advertised by the discovered service.
        port: TCP port advertised by the discovered service.
        health_url: Full URL used for `/health` validation.
        properties: TXT properties exposed by the mDNS service.
    """

    name: str
    ip: str
    port: int
    health_url: str
    properties: Mapping[str, str]


class DeviceDiscoveryPort(Protocol):
    """Port for discovering SEVA devices on the local network via mDNS."""

    def discover(self, *, duration_s: float = 2.5, health_timeout_s: float = 0.6) -> Sequence[DiscoveredBox]:
        """Browse local mDNS services and return validated devices.

        Args:
            duration_s: Total Zeroconf browse window in seconds.
            health_timeout_s: Timeout used for validating `/health`.

        Returns:
            A sequence of discovered and health-validated devices.

        Raises:
            DiscoveryAdapterError: When Zeroconf browse setup fails.
        """
        ...
