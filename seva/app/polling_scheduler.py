from __future__ import annotations

"""Scheduling helper that owns polling timers for run flows.

Inputs:
- schedule(callback, delay_ms)
- cancel(handle)

Outputs:
- stores and cancels timer handles for each group
"""


class PollingScheduler:
    """Placeholder for polling logic extracted from main.py."""

    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs
