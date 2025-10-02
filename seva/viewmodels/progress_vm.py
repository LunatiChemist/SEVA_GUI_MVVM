from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

WellId = str
BoxId = str


@dataclass
class ProgressVM:
    """Owns polling state and aggregates status for RunOverview & ChannelActivity.

    - Timer/backoff handled by Infra later; here we expose hooks and state bags
    - Receives consolidated status (e.g., from PollGroupStatus use case)
    - Translates to View DTOs
    """

    on_update_run_overview: Optional[Callable[[Dict], None]] = (
        None  # Dict with box & well rows
    )
    on_update_channel_activity: Optional[Callable[[Dict], None]] = (
        None  # WellId -> status
    )

    run_group_id: Optional[str] = None
    last_snapshot: Dict = field(default_factory=dict)

    def set_run_group(self, run_id: Optional[str]) -> None:
        self.run_group_id = run_id

    def apply_snapshot(self, snap: Dict) -> None:
        """Accepts a normalized snapshot from use case and forwards to views.
        Expected keys (informal):
          {
            'boxes': { 'A': {'phase': 'Running', 'progress': 42, 'subrun': 'A-123'}, ...},
            'wells': [('A1','Running', 40, '', 'A-123'), ...],
            'activity': {'A1':'Running', 'A2':'Idle', ...}
          }
        """
        self.last_snapshot = dict(snap)
        if self.on_update_run_overview:
            self.on_update_run_overview(
                {
                    "boxes": snap.get("boxes", {}),
                    "wells": snap.get("wells", []),
                }
            )
        if self.on_update_channel_activity:
            self.on_update_channel_activity(snap.get("activity", {}))
