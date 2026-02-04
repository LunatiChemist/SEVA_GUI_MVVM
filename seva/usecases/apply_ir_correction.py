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
    """Use-case callable for future iR correction processing."""

    def __call__(self, rs_ohm_text: str, files: Dict[str, str]) -> Dict:
        """Return a passthrough mapping until processing logic is introduced.

        Args:
            rs_ohm_text: Raw iR value entered in the UI. Accepted but not used yet.
            files: Mapping of run identifiers to file paths generated upstream.

        Returns:
            Dict: Shallow copy of the input ``files`` mapping.

        Side Effects:
            None.

        Call Chain:
            Processing trigger -> ``ApplyIRCorrection.__call__`` -> passthrough.

        Usage:
            Keeps a stable orchestration boundary while real correction is pending.

        Raises:
            None.
        """
        return {k: v for k, v in files.items()}
