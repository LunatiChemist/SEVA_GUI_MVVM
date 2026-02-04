"""Discovery-focused use cases built on `DeviceDiscoveryPort`.

`DiscoverDevices` probes candidates, while `MergeDiscoveredIntoRegistry`
combines discovered results with existing alias-to-url mappings.
"""

# seva/usecases/discover_devices.py
from __future__ import annotations
from typing import Dict, List, Optional
from seva.domain.discovery import DeviceDiscoveryPort, DiscoveredBox

class DiscoverDevices:
    """Use case: network scan using a discovery port."""

    def __init__(self, port: DeviceDiscoveryPort):
        """Bind the discovery adapter used for network probing.

        Args:
            port: Adapter implementing candidate probing and metadata retrieval.
        """
        self._port = port

    def __call__(
        self,
        *,
        candidates: List[str],
        api_key: Optional[str] = None,
        timeout_s: float = 0.3
    ) -> List[DiscoveredBox]:
        """Probe candidate URLs/networks and return discovered boxes.

        Args:
            candidates: Candidate hosts, URLs, or CIDR ranges to probe.
            api_key: Optional API key used by secured endpoints.
            timeout_s: Per-probe timeout in seconds.

        Returns:
            List[DiscoveredBox]: Discovery hits enriched by the adapter.

        Side Effects:
            Performs network calls through ``DeviceDiscoveryPort.discover``.
        """
        return self._port.discover(candidates=candidates, api_key=api_key, timeout_s=timeout_s)

class MergeDiscoveredIntoRegistry:
    """
    Merge discovered boxes into alias->base_url registry.
    - Does not drop existing aliases.
    - Adds new entries with a unique alias (prefer box_id/build; fallback to host).
    """

    def __call__(self, *, discovered: List[DiscoveredBox], registry: Dict[str, str]) -> Dict[str, str]:
        """Merge discovery hits into an alias registry without overwriting URLs.

        Args:
            discovered: Adapter results from ``DiscoverDevices``.
            registry: Existing alias-to-url mapping from settings storage.

        Returns:
            Dict[str, str]: New mapping with discovered URLs added.

        Side Effects:
            None. Returns a copy and leaves ``registry`` unchanged.
        """
        out = dict(registry)  # copy
        existing_urls = set(out.values())

        for box in discovered:
            if box.base_url in existing_urls:
                continue
            # Prefer explicit identifiers, then build tag, then URL fallback.
            alias = box.box_id or (box.build or "").strip() or box.base_url
            alias = alias or box.base_url
            base_alias = alias
            i = 1
            while alias in out:
                i += 1
                alias = f"{base_alias}-{i}"
            out[alias] = box.base_url
            existing_urls.add(box.base_url)
        return out
