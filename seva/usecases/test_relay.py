from __future__ import annotations
from dataclasses import dataclass
from ..domain.ports import RelayPort, UseCaseError


@dataclass
class TestRelay:
    relay: RelayPort

    def __call__(self, ip: str, port: int) -> bool:
        try:
            return self.relay.test(ip, port)
        except Exception as exc:  # pragma: no cover - defensive
            raise UseCaseError("RELAY_TEST_FAILED", str(exc))
