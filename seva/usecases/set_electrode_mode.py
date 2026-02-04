"""Use case for switching relay electrode modes.

The use case wraps relay operations and maps failures into `UseCaseError` for
consistent UI error presentation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from ..domain.ports import RelayPort, UseCaseError


@dataclass
class SetElectrodeMode:
    """Use-case callable for relay electrode mode changes.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    relay: RelayPort

    def __call__(self, mode: Literal["2E", "3E"]) -> None:
        """Set relay electrode mode via the configured relay port.

        Args:
            mode: Relay mode token accepted by the hardware adapter.

        Returns:
            None.

        Side Effects:
            Sends a relay command over the configured adapter implementation.

        Call Chain:
            Settings action -> ``SetElectrodeMode.__call__`` ->
            ``RelayPort.set_electrode_mode``.

        Usage:
            Used by settings diagnostics when the operator toggles 2E/3E.

        Raises:
            UseCaseError: If relay communication fails.
        """
        try:
            self.relay.set_electrode_mode(mode)
        except Exception as exc:  # pragma: no cover - defensive
            raise UseCaseError("RELAY_SET_MODE_FAILED", str(exc))

