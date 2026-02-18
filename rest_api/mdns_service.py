"""mDNS service registration for the FastAPI box API."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

SERVICE_TYPE = "_myapp._tcp.local."
SERVICE_PORT = 8000


@dataclass
class MdnsRegistrar:
    """Register and unregister the local `_myapp._tcp.local.` service."""

    hostname: str
    ip_address: str
    port: int = SERVICE_PORT

    def __post_init__(self) -> None:
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None

    def register(self) -> None:
        """Register the local service on IPv4 mDNS."""
        service_name = f"{self.hostname}.{SERVICE_TYPE}"
        self._service_info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(self.ip_address)],
            port=self.port,
            properties={
                b"health": b"/health",
                b"api": b"fastapi",
                b"port": str(self.port).encode("utf-8"),
            },
            server=f"{self.hostname}.local.",
        )
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._zeroconf.register_service(self._service_info)

    def deregister(self) -> None:
        """Cleanly deregister the mDNS service and close sockets."""
        if self._zeroconf and self._service_info:
            self._zeroconf.unregister_service(self._service_info)
        if self._zeroconf:
            self._zeroconf.close()
        self._service_info = None
        self._zeroconf = None


def resolve_local_ipv4() -> str:
    """Return the primary local IPv4 used for outbound LAN traffic."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    finally:
        probe.close()
