from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from ..domain.ports import RelayPort, UseCaseError


@dataclass
class SetElectrodeMode:
    relay: RelayPort

    def __call__(self, mode: Literal["2E", "3E"]) -> None:
        try:
            self.relay.set_electrode_mode(mode)
        except Exception as exc:  # pragma: no cover - defensive
            raise UseCaseError("RELAY_SET_MODE_FAILED", str(exc))

