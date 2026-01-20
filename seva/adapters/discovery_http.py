# seva/adapters/discovery_http.py
from __future__ import annotations
from typing import Optional, Sequence, List, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import socket
import requests

from seva.domain.discovery import DeviceDiscoveryPort, DiscoveredBox

DEFAULT_PORT = 8000

def _normalize_candidate(x: str, default_port: int) -> str:
    """Return base_url from a host or base_url; add scheme/port if missing."""
    x = x.strip()
    if not x:
        raise ValueError("empty candidate")
    if x.startswith("http://") or x.startswith("https://"):
        return x.rstrip("/")
    # host[:port]?
    if ":" in x and all(part.isdigit() for part in x.split(":")[-1:]):
        host, port = x.rsplit(":", 1)
        return f"http://{host}:{port}"
    return f"http://{x}:{default_port}"

def _try_expand_cidr(candidate: str) -> Optional[Iterable[str]]:
    try:
        network = ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        return None
    return (str(ip) for ip in network.hosts())

class HttpDiscoveryAdapter(DeviceDiscoveryPort):
    """
    KISS HTTP discovery:
      1) GET /version (no auth) to detect a SEVA box.
      2) GET /health (no auth, now allowed) to enrich with box_id/devices.
    """
    def __init__(self, default_port: int = DEFAULT_PORT, max_workers: int = 64):
        self._port = default_port
        self._max_workers = max_workers

    def discover(
        self,
        candidates: Sequence[str],
        api_key: Optional[str] = None,  # not used for MVP (health is open)
        timeout_s: float = 0.3
    ) -> List[DiscoveredBox]:
        # Normalize/expand: candidates can be base_urls, hosts, or CIDR strings
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

        # Threaded probe
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
        try:
            vresp = requests.get(f"{base_url}/version", timeout=timeout_s)
            if vresp.status_code != 200:
                return None
            vjson = vresp.json()
        except Exception:
            return None

        api_version = vjson.get("api")
        build = vjson.get("build")

        # Optional enrich via /health (now open)
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
