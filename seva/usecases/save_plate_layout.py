from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable
from ..domain.ports import StoragePort, UseCaseError, WellId


@dataclass
class SavePlateLayout:
    storage: StoragePort

    def __call__(self, name: str, wells: Iterable[WellId], params: Dict) -> None:
        try:
            self.storage.save_layout(name, wells, params)
        except Exception as e:
            raise UseCaseError("SAVE_LAYOUT_FAILED", str(e))
