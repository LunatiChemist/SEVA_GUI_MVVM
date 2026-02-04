"""Scheduler helper that owns poll timers for UI-driven run flows.

The presenter layer passes Tk ``after`` and ``after_cancel`` callables into
this class so timer state can be tracked in one place and canceled safely when
groups stop or the app closes.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Callable, Dict, Optional


ScheduleFn = Callable[[int, Callable[[], None]], str]
CancelFn = Callable[[str], None]


@dataclass
class PollHandle:
    """Timer token associated with a single poll channel.

    Attributes:
        group_id: Channel key (run-group id or synthetic key like ``activity``).
        token: Scheduler token returned by the UI scheduler implementation.
    """
    group_id: str
    token: str


class PollingScheduler:
    """Manage per-group polling timers using a UI scheduler (for example Tk)."""

    def __init__(self, schedule: ScheduleFn, cancel: CancelFn) -> None:
        """Store schedule/cancel functions and initialize handle registry.

        Args:
            schedule: Function compatible with ``after(delay_ms, callback)``.
            cancel: Function compatible with ``after_cancel(token)``.
        """
        self._schedule = schedule
        self._cancel = cancel
        self._handles: Dict[str, PollHandle] = {}

    def schedule(self, group_id: str, delay_ms: int, callback: Callable[[], None]) -> None:
        """Schedule or reschedule the next poll for a group.

        Args:
            group_id: Poll channel key.
            delay_ms: Delay in milliseconds before callback execution.
            callback: Poll callback to execute.
        """
        delay = max(1, int(delay_ms))
        self.cancel(group_id)
        token = self._schedule(delay, callback)
        self._handles[group_id] = PollHandle(group_id=group_id, token=token)

    def cancel(self, group_id: str) -> None:
        """Cancel a pending poll for a group.

        Args:
            group_id: Poll channel key to cancel.
        """
        handle = self._handles.pop(group_id, None)
        if not handle:
            return
        try:
            self._cancel(handle.token)
        except Exception:
            pass

    def cancel_all(self) -> None:
        """Cancel all pending polls across all channel keys."""
        for group_id in list(self._handles.keys()):
            self.cancel(group_id)

    def handle_for(self, group_id: str) -> Optional[PollHandle]:
        """Return the current handle for a channel, if scheduled."""
        return self._handles.get(group_id)


__all__ = ["PollHandle", "PollingScheduler"]
