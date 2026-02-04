"""Use-case placeholder for iR correction post-processing.

This module currently returns passthrough results and marks where future
processing-specific logic will be introduced.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

# Placeholder: real processing will live in processing/* modules


@dataclass
class ApplyIRCorrection:
    """Use-case callable for iR correction processing.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    def __call__(self, rs_ohm_text: str, files: Dict[str, str]) -> Dict:
        """Return a lightweight result mapping. No actual math here yet."""
        return {k: v for k, v in files.items()}
