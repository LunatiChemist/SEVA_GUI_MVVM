"""Mock relay adapter for non-hardware environments.

Dependencies:
    - ``RelayPort`` protocol from ``seva.domain.ports``.

Call context:
    - Wired by ``seva/app/main.py`` for ``TestRelay`` and
      ``SetElectrodeMode`` use cases when no real relay adapter is configured.
"""

from __future__ import annotations
from typing import Literal
from seva.domain.ports import RelayPort


class RelayMock(RelayPort):
    """No-op ``RelayPort`` implementation for tests and local development."""

    def test(self, ip: str, port: int) -> bool:
        """Report relay reachability.

        Args:
            ip: Relay host IP (ignored by mock).
            port: Relay TCP port (ignored by mock).

        Returns:
            Always ``True`` to keep connection test deterministic offline.
        """
        return True

    def set_electrode_mode(self, mode: Literal["2E", "3E"]) -> None:
        """Accept electrode mode change without hardware side effects.

        Args:
            mode: Requested relay mode token.

        Side Effects:
            None. This mock intentionally performs no external I/O.
        """
        # No relay hardware is controlled in the mock implementation.
        return None
