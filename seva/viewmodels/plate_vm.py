"""Plate-grid selection state for ``WellGridView`` interactions.

Call context:
    ``seva/app/main.py`` instantiates :class:`PlateVM`, then binds view events
    (selection changes, copy/paste, submit, enable toggles) to this module.

This module keeps only UI state and intent callbacks. Persistence, networking,
and workflow orchestration are delegated to use-case/presenter layers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from ..domain.util import well_id_to_box

WellId = str  # e.g., "A1"
BoxId = str   # e.g., "A"


@dataclass
class PlateVM:
    """Hold plate selection and configuration state for the grid.

    Attributes:
        on_selection_changed: Callback fired after ``set_selection`` updates.
        on_submit_requested: Callback fired by ``cmd_submit``.
        on_copy_from: Callback fired by ``cmd_copy_from``.
        on_paste_to_selection: Callback fired by ``cmd_paste_to_selection``.
        on_toggle_enable_selection: Callback for toggling selected wells.
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
        """Replace selected wells and notify listeners.

        Args:
            wells: Selected well ids emitted by ``WellGridView``.

        Side Effects:
            Updates ``_selected`` and calls ``on_selection_changed`` when set.
        """
        self._selected = set(wells)
        if self.on_selection_changed:
            self.on_selection_changed(self._selected)

    def get_selection(self) -> Set[WellId]:
        """Return a defensive copy of current selection state."""
        return set(self._selected)

    # ---- Configured state ----
    def mark_configured(self, wells: Iterable[WellId]) -> Set[WellId]:
        """Mark wells as configured and return the new configured set."""
        self._configured.update(wells)
        return set(self._configured)

    def clear_configured(self, wells: Iterable[WellId]) -> Set[WellId]:
        """Clear configured markers for specific wells."""
        for w in wells:
            self._configured.discard(w)
        return set(self._configured)

    def clear_all_configured(self) -> None:
        """Remove all configured markers."""
        self._configured.clear()

    def configured(self) -> Set[WellId]:
        """Return a defensive copy of configured wells."""
        return set(self._configured)

    # ---- Commands surfaced to View ----
    def cmd_submit(self) -> None:
        """Emit submit intent to higher-level orchestration."""
        if self.on_submit_requested:
            self.on_submit_requested()

    def cmd_copy_from(self, source: WellId) -> None:
        """Emit copy-from-well intent for the selected source well."""
        if self.on_copy_from:
            self.on_copy_from(source)

    def cmd_paste_to_selection(self) -> None:
        """Emit paste intent using current selection snapshot."""
        if self.on_paste_to_selection:
            self.on_paste_to_selection(set(self._selected))

    def cmd_toggle_enable_selection(self) -> None:
        """Emit enable-toggle intent scoped to current selection."""
        if self.on_toggle_enable_selection:
            self.on_toggle_enable_selection(set(self._selected))

    # ---- Helpers ----
    @staticmethod
    def well_to_box(well_id: WellId) -> BoxId:
        """Validate a well id and return its box prefix token.

        Usage scenario:
            Used by UI glue when deriving per-box actions from selected wells.

        Args:
            well_id: Well token such as ``A1``.

        Returns:
            BoxId: Prefix token such as ``A``.

        Raises:
            ValueError: If the token is empty or does not match expected shape.
        """
        if not well_id:
            raise ValueError("Empty well_id")
        text = well_id.strip()
        if len(text) < 2:
            raise ValueError(f"Invalid well id '{well_id}'")
        suffix = text[1:]
        if not suffix.isdigit():
            raise ValueError(f"Invalid well id '{well_id}'")
        number = int(suffix)
        if number <= 0:
            raise ValueError(f"Invalid well id '{well_id}'")
        prefix = well_id_to_box(text)
        if not prefix:
            raise ValueError(f"Invalid box prefix in well id '{well_id}'")
        return prefix
