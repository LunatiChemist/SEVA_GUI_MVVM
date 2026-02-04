"""Use case for relay connectivity diagnostics.

The workflow delegates to `RelayPort.test` and maps exceptions into use-case
error codes for UI display.
"""

from __future__ import annotations
from dataclasses import dataclass
from ..domain.ports import RelayPort, UseCaseError


@dataclass
class TestRelay:
    """Use-case callable for relay diagnostics.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    relay: RelayPort

    def __call__(self, ip: str, port: int) -> bool:
        try:
            return self.relay.test(ip, port)
        except Exception as exc:  # pragma: no cover - defensive
            raise UseCaseError("RELAY_TEST_FAILED", str(exc))
