"""Scheduling helper that owns polling timers for run flows."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Callable, Dict, Optional


ScheduleFn = Callable[[int, Callable[[], None]], str]
CancelFn = Callable[[str], None]


@dataclass
class PollHandle:
    """Polling token container for one active run-group timer.
    
    Attributes:
        Members are consumed by controllers, presenters, or Tk views.
    """
    group_id: str
    token: str


class PollingScheduler:
    """Manage per-group polling timers using a UI scheduler (e.g., Tk after)."""

    def __init__(self, schedule: ScheduleFn, cancel: CancelFn) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._handles: Dict[str, PollHandle] = {}

    def schedule(self, group_id: str, delay_ms: int, callback: Callable[[], None]) -> None:
        """Schedule or reschedule the next poll for a group."""
        delay = max(1, int(delay_ms))
        self.cancel(group_id)
        token = self._schedule(delay, callback)
        self._handles[group_id] = PollHandle(group_id=group_id, token=token)

    def cancel(self, group_id: str) -> None:
        """Cancel a pending poll for a group (no-op if none)."""
        handle = self._handles.pop(group_id, None)
        if not handle:
            return
        try:
            self._cancel(handle.token)
        except Exception:
            pass

    def cancel_all(self) -> None:
        """Cancel all pending polls."""
        for group_id in list(self._handles.keys()):
            self.cancel(group_id)

    def handle_for(self, group_id: str) -> Optional[PollHandle]:
        return self._handles.get(group_id)


__all__ = ["PollHandle", "PollingScheduler"]
