from __future__ import annotations

"""UI-facing presenter that coordinates run flow actions without view logic.

Inputs:
- callbacks or UI adapters for start/cancel/poll notifications
- use cases and coordinators for run flow orchestration

Outputs:
- invokes hooks/callbacks when run state changes
- returns run identifiers and context data to the caller
"""


class RunFlowPresenter:
    """Placeholder for run-flow orchestration extracted from main.py."""

    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs
