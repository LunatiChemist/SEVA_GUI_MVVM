from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from ..domain.ports import StoragePort, UseCaseError


@dataclass
class LoadPlateLayout:
    storage: StoragePort

    def __call__(self, name: str) -> Dict:
        try:
            return self.storage.load_layout(name)
        except Exception as e:
            raise UseCaseError("LOAD_LAYOUT_FAILED", str(e))
