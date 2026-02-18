"""Discovery-focused use cases built on ``DeviceDiscoveryPort``."""

from __future__ import annotations

from typing import Dict, List, Sequence

from seva.domain.discovery import DeviceDiscoveryPort, DiscoveredBox


class DiscoverDevices:
    """Use case that runs mDNS discovery through a discovery port."""

    def __init__(self, port: DeviceDiscoveryPort):
        self._port = port

    def __call__(
        self,
        *,
        duration_s: float = 2.5,
        health_timeout_s: float = 0.6,
    ) -> Sequence[DiscoveredBox]:
        """Return discovered and health-validated boxes."""
        return self._port.discover(duration_s=duration_s, health_timeout_s=health_timeout_s)


class MergeDiscoveredIntoRegistry:
    """Merge discovered boxes into alias->base_url registry with unique aliases."""

    def __call__(self, *, discovered: List[DiscoveredBox], registry: Dict[str, str]) -> Dict[str, str]:
        out = dict(registry)
        existing_urls = set(out.values())

        for box in discovered:
            base_url = f"http://{box.ip}:{box.port}"
            if base_url in existing_urls:
                continue
            alias = (box.name or "device").strip() or "device"
            base_alias = alias
            suffix = 2
            while alias in out:
                alias = f"{base_alias}-{suffix}"
                suffix += 1
            out[alias] = base_url
            existing_urls.add(base_url)
        return out
