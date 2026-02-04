"""HTTP discovery adapter for finding reachable SEVA boxes.

This adapter implements ``DeviceDiscoveryPort`` by probing network candidates
against lightweight public endpoints. It is intentionally side-effect free
outside network calls and returns domain ``DiscoveredBox`` objects.

Dependencies:
    - ``requests`` for probing HTTP endpoints.
    - ``concurrent.futures.ThreadPoolExecutor`` for parallel host checks.
    - ``ipaddress`` for CIDR expansion.

Call context:
    - Invoked by ``DiscoverDevices`` and ``DiscoverAndAssignDevices`` use cases.
"""

# seva/adapters/discovery_http.py
from __future__ import annotations
from typing import Optional, Sequence, List, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import requests

from seva.domain.discovery import DeviceDiscoveryPort, DiscoveredBox

DEFAULT_PORT = 8000


def _normalize_candidate(x: str, default_port: int) -> str:
    """Normalize host/base-url candidate to canonical base URL.

    Args:
        x: Candidate host, host:port, or full ``http(s)://`` base URL.
        default_port: Port used when host does not include a port.

    Returns:
        Canonical base URL without trailing slash.

    Raises:
        ValueError: If candidate is empty after whitespace trimming.
    """
    x = x.strip()
    if not x:
        raise ValueError("empty candidate")
    if x.startswith("http://") or x.startswith("https://"):
        return x.rstrip("/")
    # Handle ``host:port`` input without scheme.
    if ":" in x and all(part.isdigit() for part in x.split(":")[-1:]):
        host, port = x.rsplit(":", 1)
        return f"http://{host}:{port}"
    return f"http://{x}:{default_port}"


def _try_expand_cidr(candidate: str) -> Optional[Iterable[str]]:
    """Expand CIDR notation into host IP strings when possible.

    Args:
        candidate: Candidate string that may contain CIDR notation.

    Returns:
        Host iterator for valid CIDR input, otherwise ``None``.
    """
    try:
        network = ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        return None
    return (str(ip) for ip in network.hosts())


class HttpDiscoveryAdapter(DeviceDiscoveryPort):
    """Probe candidate hosts and return discovered SEVA boxes.

    Discovery strategy:
        1. ``GET /version`` identifies a compatible service.
        2. ``GET /health`` enriches result with ``box_id`` and ``devices``.
    """

    def __init__(self, default_port: int = DEFAULT_PORT, max_workers: int = 64):
        """Create discovery adapter.

        Args:
            default_port: Port applied to host-only candidates.
            max_workers: Thread-pool size used for parallel probing.
        """
        self._port = default_port
        self._max_workers = max_workers

    def discover(
        self,
        candidates: Sequence[str],
        api_key: Optional[str] = None,  # not used for MVP (health is open)
        timeout_s: float = 0.3
    ) -> List[DiscoveredBox]:
        """Discover boxes from host/base-url/CIDR candidates.

        Args:
            candidates: Candidate strings entered by user/settings layer.
            api_key: Unused for current endpoints (kept for port compatibility).
            timeout_s: Per-request timeout in seconds.

        Returns:
            List of unique ``DiscoveredBox`` records.

        Side Effects:
            Performs parallel network requests to candidate hosts.

        Call Chain:
            Settings controller -> discovery use case -> ``discover``.
        """
        # Normalize/expand candidates before probing.
        base_urls: List[str] = []
        for c in candidates:
            c = c.strip()
            if not c:
                continue
            cidr_hosts = _try_expand_cidr(c)
            if cidr_hosts is not None:
                for host in cidr_hosts:
                    base_urls.append(_normalize_candidate(host, self._port))
            else:
                base_urls.append(_normalize_candidate(c, self._port))

        # Probe in parallel to keep settings dialog responsive on large subnets.
        results: List[DiscoveredBox] = []
        seen = set()
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futs = {pool.submit(self._probe_single, url, timeout_s): url for url in base_urls}
            for fut in as_completed(futs):
                box = fut.result()
                if box and box.base_url not in seen:
                    seen.add(box.base_url)
                    results.append(box)
        return results

    def _probe_single(self, base_url: str, timeout_s: float) -> Optional[DiscoveredBox]:
        """Probe a single base URL and build a discovery record.

        Args:
            base_url: Canonical base URL candidate.
            timeout_s: Per-request timeout in seconds.

        Returns:
            ``DiscoveredBox`` when probe succeeds, else ``None``.
        """
        try:
            vresp = requests.get(f"{base_url}/version", timeout=timeout_s)
            if vresp.status_code != 200:
                return None
            vjson = vresp.json()
        except Exception:
            return None

        api_version = vjson.get("api")
        build = vjson.get("build")

        # Health enrichment is best-effort; discovery still succeeds without it.
        box_id = None
        devices = None
        try:
            hresp = requests.get(f"{base_url}/health", timeout=timeout_s)
            if hresp.status_code == 200:
                hjson = hresp.json()
                box_id = hjson.get("box_id")
                devices = hjson.get("devices")
        except Exception:
            pass

        return DiscoveredBox(
            base_url=base_url,
            api_version=api_version,
            build=build,
            box_id=box_id,
            devices=devices,
        )
