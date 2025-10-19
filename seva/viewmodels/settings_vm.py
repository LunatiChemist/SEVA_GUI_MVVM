from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from ..utils.logging import env_requests_debug

BoxId = str


def _default_debug_logging() -> bool:
    return env_requests_debug()


@dataclass
class SettingsVM:
    """Keeps app settings UI state and validation, no I/O here.

    - Provides derived flag to enable Save button
    - Emits events to Browse/Tests; persistence via UseCases/Ports
    """

    on_test_connection: Optional[Callable[[BoxId], None]] = None
    on_test_relay: Optional[Callable[[], None]] = None
    on_browse_results_dir: Optional[Callable[[], None]] = None
    on_save: Optional[Callable[[dict], None]] = None

    box_urls: Dict[BoxId, str] = field(
        default_factory=lambda: {b: "" for b in ("A", "B", "C", "D")}
    )
    api_keys: Dict[BoxId, str] = field(
        default_factory=lambda: {b: "" for b in ("A", "B", "C", "D")}
    )
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    poll_interval_ms: int = 750
    results_dir: str = "."
    experiment_name: str = ""
    subdir: str = ""
    use_streaming: bool = False
    relay_ip: str = ""
    relay_port: int = 0
    debug_logging: bool = field(default_factory=_default_debug_logging)

    def is_valid(self) -> bool:
        # Minimal validation (extend later): URLs filled where used; ports numeric
        if any(v and not isinstance(v, str) for v in self.box_urls.values()):
            return False
        if self.relay_port < 0:
            return False
        return True

    def apply_dict(self, payload: Dict) -> None:
        """
        Apply persisted settings to the view-model.

        Expects a flat payload with keys such as `box_urls`, `api_keys`,
        `request_timeout_s`, `download_timeout_s`, `poll_interval_ms`,
        `results_dir`, `experiment_name`, `subdir`, `use_streaming`,
        `debug_logging`, and `relay`.

        Legacy nested formats (e.g. a `timeouts` dict) are no longer supported.
        """
        if not isinstance(payload, dict):
            return

        if "timeouts" in payload and payload.get("timeouts") is not None:
            raise ValueError(
                "Unsupported settings format (legacy). Please re-save settings."
            )

        box_urls = payload.get("box_urls")
        if isinstance(box_urls, dict):
            self.box_urls = dict(box_urls)

        api_keys = payload.get("api_keys")
        if isinstance(api_keys, dict):
            self.api_keys = dict(api_keys)

        if "request_timeout_s" in payload:
            value = payload.get("request_timeout_s")
            if isinstance(value, (int, float)):
                self.request_timeout_s = int(value)

        if "download_timeout_s" in payload:
            value = payload.get("download_timeout_s")
            if isinstance(value, (int, float)):
                self.download_timeout_s = int(value)

        if "poll_interval_ms" in payload:
            value = payload.get("poll_interval_ms")
            if isinstance(value, (int, float)):
                self.poll_interval_ms = int(value)

        if "results_dir" in payload:
            value = payload.get("results_dir")
            if isinstance(value, str):
                self.results_dir = value

        if "experiment_name" in payload:
            value = payload.get("experiment_name")
            if isinstance(value, str):
                self.experiment_name = value

        if "subdir" in payload:
            value = payload.get("subdir")
            if isinstance(value, str):
                self.subdir = value

        if "use_streaming" in payload:
            value = payload.get("use_streaming")
            if isinstance(value, bool):
                self.use_streaming = value

        if "debug_logging" in payload:
            value = payload.get("debug_logging")
            if isinstance(value, bool):
                self.debug_logging = value
            elif value is not None:
                self.debug_logging = bool(value)

        relay = payload.get("relay")
        if isinstance(relay, dict):
            ip = relay.get("ip")
            if isinstance(ip, str) or ip is None:
                self.relay_ip = ip or ""
            port = relay.get("port")
            if isinstance(port, (int, float)):
                self.relay_port = int(port)

    def to_dict(self) -> dict:
        return {
            "box_urls": dict(self.box_urls),
            "api_keys": dict(self.api_keys),
            "request_timeout_s": self.request_timeout_s,
            "download_timeout_s": self.download_timeout_s,
            "poll_interval_ms": self.poll_interval_ms,
            "results_dir": self.results_dir,
            "experiment_name": self.experiment_name,
            "subdir": self.subdir,
            "use_streaming": bool(self.use_streaming),
            "relay": {"ip": self.relay_ip, "port": self.relay_port},
            "debug_logging": bool(self.debug_logging),
        }

    def set_results_dir(self, path: str) -> None:
        if not isinstance(path, str):
            return
        normalized = path.strip() or "."
        self.results_dir = normalized

    def set_debug_logging(self, enabled: bool) -> None:
        self.debug_logging = bool(enabled)

    # Commands
    def cmd_save(self) -> None:
        if not self.is_valid():
            raise ValueError("Settings invalid")
        if self.on_save:
            self.on_save(self.to_dict())

    def set_experiment_name(self, name: str) -> None:
        """Apply a trimmed experiment name provided by the UI."""
        if isinstance(name, str):
            self.experiment_name = name.strip()

    def set_subdir(self, value: str) -> None:
        """Apply an optional sub-directory name provided by the UI."""
        if isinstance(value, str):
            self.subdir = value.strip()
