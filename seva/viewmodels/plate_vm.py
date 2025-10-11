from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

WellId = str  # e.g., "A1"
BoxId = str   # e.g., "A"


@dataclass
class PlateVM:
    """Holds WellGrid state: selection, configured wells. Pure UI-logic.

    Responsibilities
    - Manage selection & configured wells (green state in WellGridView)
    - Provide commands for Apply Params, Submit (signals only)
    - Map WellId -> BoxId purely by prefix (A/B/C/D); no 1..40 math
    - Persist/restore layout via StoragePort (delegated to UseCases)

    Future: LiveData could be added here.
    """

    on_selection_changed: Optional[Callable[[Set[WellId]], None]] = None
    on_submit_requested: Optional[Callable[[], None]] = None
    on_copy_from: Optional[Callable[[WellId], None]] = None
    on_paste_to_selection: Optional[Callable[[Set[WellId]], None]] = None
    on_toggle_enable_selection: Optional[Callable[[Set[WellId]], None]] = None

    _selected: Set[WellId] = field(default_factory=set)
    _configured: Set[WellId] = field(default_factory=set)
    _boxes: Tuple[BoxId, ...] = ("A", "B", "C", "D")

    # ---- Selection API (called by View) ----
    def set_selection(self, wells: Iterable[WellId]) -> None:
        self._selected = set(wells)
        if self.on_selection_changed:
            self.on_selection_changed(self._selected)

    def get_selection(self) -> Set[WellId]:
        return set(self._selected)

    # ---- Configured state ----
    def mark_configured(self, wells: Iterable[WellId]) -> Set[WellId]:
        self._configured.update(wells)
        return set(self._configured)

    def clear_configured(self, wells: Iterable[WellId]) -> Set[WellId]:
        for w in wells:
            self._configured.discard(w)
        return set(self._configured)

    def clear_all_configured(self) -> None:
        self._configured.clear()

    def configured(self) -> Set[WellId]:
        return set(self._configured)

    # ---- Commands surfaced to View ----
    def cmd_submit(self) -> None:
        if self.on_submit_requested:
            self.on_submit_requested()

    def cmd_copy_from(self, source: WellId) -> None:
        if self.on_copy_from:
            self.on_copy_from(source)

    def cmd_paste_to_selection(self) -> None:
        if self.on_paste_to_selection:
            self.on_paste_to_selection(set(self._selected))

    def cmd_toggle_enable_selection(self) -> None:
        if self.on_toggle_enable_selection:
            self.on_toggle_enable_selection(set(self._selected))

    # ---- Helpers ----
    @staticmethod
    def well_to_box(well_id: WellId) -> BoxId:
        if not well_id:
            raise ValueError("Empty well_id")
        if len(well_id) < 2:
            raise ValueError(f"Invalid well id '{well_id}'")
        suffix = well_id[1:]
        if not suffix.isdigit():
            raise ValueError(f"Invalid well id '{well_id}'")
        number = int(suffix)
        if number <= 0:
            raise ValueError(f"Invalid well id '{well_id}'")
        prefix = well_id[0].upper()
        if prefix not in {"A", "B", "C", "D"}:
            raise ValueError(f"Invalid box prefix: {prefix}")
        return prefix
