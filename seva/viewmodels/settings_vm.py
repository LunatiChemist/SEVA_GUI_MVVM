from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

BoxId = str


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
    use_streaming: bool = False
    relay_ip: str = ""
    relay_port: int = 0

    def is_valid(self) -> bool:
        # Minimal validation (extend later): URLs filled where used; ports numeric
        if any(v and not isinstance(v, str) for v in self.box_urls.values()):
            return False
        if self.relay_port < 0:
            return False
        return True

    def build_settings_dict(self) -> dict:
        return {
            "box_urls": dict(self.box_urls),
            "api_keys": dict(self.api_keys),
            "timeouts": {
                "request_s": self.request_timeout_s,
                "download_s": self.download_timeout_s,
            },
            "poll_interval_ms": self.poll_interval_ms,
            "results_dir": self.results_dir,
            "use_streaming": bool(self.use_streaming),
            "relay": {"ip": self.relay_ip, "port": self.relay_port},
        }

    # Commands
    def cmd_save(self) -> None:
        if not self.is_valid():
            raise ValueError("Settings invalid")
        if self.on_save:
            self.on_save(self.build_settings_dict())
