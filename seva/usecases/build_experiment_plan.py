from __future__ import annotations

"""Use case for assembling a domain ExperimentPlan from UI-provided inputs."""

from dataclasses import dataclass
from typing import Any

from seva.domain.entities import ExperimentPlan


@dataclass
class BuildExperimentPlan:
    """Placeholder for plan construction extracted from ExperimentVM."""

    def __call__(self, request: Any) -> ExperimentPlan:
        raise NotImplementedError("BuildExperimentPlan is not implemented yet.")


__all__ = ["BuildExperimentPlan"]
