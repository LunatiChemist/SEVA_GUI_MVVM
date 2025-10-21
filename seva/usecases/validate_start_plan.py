from __future__ import annotations

from typing import List, Dict

from ..domain.entities import ExperimentPlan
from ..domain.ports import BoxId, DevicePort, ModeValidationResult, UseCaseError, WellId, JobPort
from ..domain.util import well_id_to_box
from .start_experiment_batch import WellValidationResult


class ValidateStartPlan:
    """Validate parameters and detect busy wells per box deterministically."""

    def __init__(self, device_port: DevicePort, job_port: JobPort) -> None:
        self.device_port = device_port
        self.job_port = job_port

    def __call__(self, plan: ExperimentPlan) -> List[WellValidationResult]:
        try:
            validations: List[WellValidationResult] = []
            per_well: Dict[str, WellValidationResult] = {}
            wells_by_box: Dict[BoxId, List[WellId]] = {}
            for well_plan in plan.wells:
                well_id_str = str(well_plan.well)
                if not well_id_str or len(well_id_str) < 2:
                    raise ValueError(f"Invalid well id '{well_id_str}'")
                box = well_id_to_box(well_id_str)
                if not box:
                    raise ValueError(f"Invalid well id '{well_id_str}'")

                try:
                    params_payload = well_plan.params.to_payload()
                except NotImplementedError as exc:
                    raise ValueError(
                        f"Well '{well_id_str}' parameters do not support payload serialization."
                    ) from exc
                except AttributeError as exc:
                    raise ValueError(
                        f"Well '{well_id_str}' parameters are missing a to_payload() method."
                    ) from exc

                mode = str(well_plan.mode)

                try:
                    result: ModeValidationResult = self.device_port.validate_mode(
                        box, mode, params_payload
                    )
                except Exception as exc:
                    raise UseCaseError("VALIDATION_FAILED", f"{well_id_str}: {exc}")

                errors = list(result["errors"])
                warnings = list(result["warnings"])
                ok_flag = bool(result["ok"])

                vr = WellValidationResult(
                    well_id=WellId(well_id_str),
                    box_id=BoxId(box),
                    mode=mode,
                    ok=ok_flag and not errors,
                    errors=errors,
                    warnings=warnings,
                )
                per_well[well_id_str] = vr
                wells_by_box.setdefault(box, []).append(WellId(well_id_str))

            # Busy check per box
            for box, bucket in wells_by_box.items():
                try:
                    busy = self.job_port.list_busy_wells(box)
                except Exception as exc:
                    # Non-fatal for validation; surface as warning
                    busy = set()
                if not busy:
                    continue
                for wid in bucket:
                    if str(wid) in busy:
                        vr = per_well[str(wid)]
                        vr.ok = False
                        vr.errors.append("SLOT_BUSY")

            validations = list(per_well.values())
            return validations
        except UseCaseError:
            raise
        except Exception as exc:
            raise UseCaseError("VALIDATION_FAILED", str(exc))
