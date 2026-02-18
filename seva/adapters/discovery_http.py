"""mDNS/Zeroconf discovery adapter for SEVA devices.

This adapter browses `_myapp._tcp.local.` services for a fixed duration,
extracts IPv4 endpoints and TXT properties, validates `/health`, and returns
normalized discovery domain records.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List

import requests
from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf

from seva.domain.discovery import DeviceDiscoveryPort, DiscoveredBox, DiscoveryAdapterError

SERVICE_TYPE = "_myapp._tcp.local."


@dataclass(frozen=True)
class _Candidate:
    """Internal representation of one discovered service candidate."""

    name: str
    ip: str
    port: int
    properties: Dict[str, str]


class _MdnsListener(ServiceListener):
    """Collect candidates from Zeroconf callbacks."""

    def __init__(self, zeroconf: Zeroconf):
        self._zeroconf = zeroconf
        self._lock = threading.Lock()
        self._by_instance: Dict[str, _Candidate] = {}

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._capture(service_type, name)

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._capture(service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        with self._lock:
            self._by_instance.pop(name, None)

    def _capture(self, service_type: str, name: str) -> None:
        info = self._zeroconf.get_service_info(service_type, name, timeout=500)
        if info is None:
            return
        ipv4 = info.parsed_addresses(IPVersion.V4Only)
        if not ipv4:
            return
        ip = ipv4[0]
        if not ip:
            return

        properties: Dict[str, str] = {}
        for key, value in (info.properties or {}).items():
            text_key = key.decode("utf-8", errors="ignore") if isinstance(key, bytes) else str(key)
            text_val = value.decode("utf-8", errors="ignore") if isinstance(value, bytes) else str(value)
            if text_key:
                properties[text_key] = text_val

        instance_name = name.split(".", 1)[0].strip() or ip
        with self._lock:
            self._by_instance[name] = _Candidate(
                name=instance_name,
                ip=ip,
                port=int(info.port),
                properties=properties,
            )

    def snapshot(self) -> List[_Candidate]:
        with self._lock:
            return list(self._by_instance.values())


class HttpDiscoveryAdapter(DeviceDiscoveryPort):
    """Browse LAN mDNS services and return health-validated devices."""

    def discover(self, *, duration_s: float = 2.5, health_timeout_s: float = 0.6) -> List[DiscoveredBox]:
        """Browse `_myapp._tcp.local.` for ``duration_s`` and validate `/health`."""
        try:
            zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        except Exception as exc:
            raise DiscoveryAdapterError(f"Could not start Zeroconf browser: {exc}") from exc

        listener = _MdnsListener(zeroconf)
        browser = ServiceBrowser(zeroconf, SERVICE_TYPE, listener=listener)
        try:
            time.sleep(max(0.0, float(duration_s)))
            candidates = listener.snapshot()
        finally:
            browser.cancel()
            zeroconf.close()

        validated: List[DiscoveredBox] = []
        name_counts: Dict[str, int] = {}

        for candidate in candidates:
            health_url = f"http://{candidate.ip}:{candidate.port}/health"
            try:
                response = requests.get(health_url, timeout=max(0.1, float(health_timeout_s)))
            except requests.RequestException:
                continue
            if response.status_code != 200:
                continue

            base_name = candidate.name or candidate.ip
            used = name_counts.get(base_name, 0)
            unique_name = base_name if used == 0 else f"{base_name}-{used + 1}"
            name_counts[base_name] = used + 1

            validated.append(
                DiscoveredBox(
                    name=unique_name,
                    ip=candidate.ip,
                    port=candidate.port,
                    health_url=health_url,
                    properties=dict(candidate.properties),
                )
            )

        return validated
