"""Typed storage metadata used to build download paths and registry entries."""

from __future__ import annotations


from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from .time_utils import parse_client_datetime


@dataclass(frozen=True)
class StorageMeta:
    """Normalized storage metadata for a run group."""

    experiment: str
    subdir: Optional[str]
    client_datetime: datetime
    results_dir: str

    def __post_init__(self) -> None:
        if not isinstance(self.experiment, str) or not self.experiment.strip():
            raise ValueError("StorageMeta.experiment must be a non-empty string.")
        cleaned = self.subdir.strip() if isinstance(self.subdir, str) else None
        object.__setattr__(self, "subdir", cleaned or None)
        if not isinstance(self.results_dir, str) or not self.results_dir.strip():
            raise ValueError("StorageMeta.results_dir must be a non-empty string.")

    def client_datetime_label(self) -> str:
        return self.client_datetime.astimezone().strftime("%Y-%m-%d_%H-%M-%S")

    def to_payload(self) -> dict[str, str]:
        return {
            "experiment": self.experiment,
            "subdir": self.subdir or "",
            "client_datetime": self.client_datetime.isoformat(),
            "results_dir": self.results_dir,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "StorageMeta":
        if not isinstance(payload, Mapping):
            raise ValueError("StorageMeta payload must be a mapping.")
        experiment = str(payload.get("experiment") or "").strip()
        if not experiment:
            raise ValueError("StorageMeta payload missing experiment.")
        subdir_raw = payload.get("subdir")
        subdir = str(subdir_raw).strip() if subdir_raw is not None else None
        client_dt_raw = payload.get("client_datetime") or payload.get("client_dt")
        client_dt = parse_client_datetime(client_dt_raw)
        results_dir = str(payload.get("results_dir") or "").strip() or "."
        return cls(
            experiment=experiment,
            subdir=subdir,
            client_datetime=client_dt,
            results_dir=results_dir,
        )


__all__ = ["StorageMeta"]
