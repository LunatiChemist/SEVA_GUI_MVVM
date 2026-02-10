"""Use case for relay connectivity diagnostics.

The workflow delegates to `RelayPort.test` and maps exceptions into use-case
error codes for UI display.
"""

from __future__ import annotations
from dataclasses import dataclass
from seva.domain.ports import RelayPort, UseCaseError


@dataclass
class TestRelay:
    """Use-case callable for relay diagnostics.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    relay: RelayPort

    def __call__(self, ip: str, port: int) -> bool:
        """Run relay connectivity diagnostics for one endpoint.

        Args:
            ip: Relay host/IP configured in settings.
            port: Relay TCP port configured in settings.

        Returns:
            bool: ``True`` when relay test succeeds.

        Side Effects:
            Performs relay communication through ``RelayPort.test``.

        Call Chain:
            Settings relay test -> ``TestRelay.__call__`` -> ``RelayPort.test``.

        Usage:
            Verifies relay reachability before mode changes.

        Raises:
            UseCaseError: If the adapter reports any relay error.
        """
        try:
            return self.relay.test(ip, port)
        except Exception as exc:  # pragma: no cover - defensive
            raise UseCaseError("RELAY_TEST_FAILED", str(exc))
