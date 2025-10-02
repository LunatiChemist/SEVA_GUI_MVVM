from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

WellId = str


@dataclass
class LiveDataVM:
    """Coordinates DataPlotter view: files list, include flags, IR correction.

    - Does not perform I/O; delegates to UseCases for listing/loading/export
    - Maintains which wells are included for export and current axes/section
    """

    run_group_id: Optional[str] = None
    include: Dict[WellId, bool] = field(default_factory=dict)
    axes: Tuple[str, str] = ("E", "I")
    section: Optional[str] = None
    rs_text: str = ""

    def toggle_include(self, well_id: WellId, included: bool) -> None:
        self.include[well_id] = bool(included)
