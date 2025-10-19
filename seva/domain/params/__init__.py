"""Mode parameter data containers."""

from __future__ import annotations

from typing import Any, Dict, Mapping


class ModeParams:
    """Base type for form-derived mode parameters."""

    flags: Mapping[str, Any]

    @classmethod
    def from_form(cls, form: Dict[str, Any]) -> "ModeParams":
        """Build a params object from a UI form snapshot."""
        raise NotImplementedError

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the params into the REST API payload schema."""
        raise NotImplementedError


from .cv import CVParams  # noqa: E402

__all__ = ["ModeParams", "CVParams"]
