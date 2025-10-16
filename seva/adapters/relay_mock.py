from __future__ import annotations
from typing import Literal
from seva.domain.ports import RelayPort


class RelayMock(RelayPort):
    """In-memory relay stub used for tests and offline development."""

    def test(self, ip: str, port: int) -> bool:
        return True

    def set_electrode_mode(self, mode: Literal["2E", "3E"]) -> None:
        # Nothing to do - we just accept the mode.
        return None
