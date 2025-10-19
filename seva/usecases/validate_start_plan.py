from __future__ import annotations

from typing import List, Mapping

from ..domain.entities import ExperimentPlan
from ..domain.ports import BoxId, DevicePort, ModeValidationResult, UseCaseError, WellId
from .start_experiment_batch import WellValidationResult, build_experiment_plan


class ValidateStartPlan:
    """Run device-side validation for each well in the supplied plan."""

    def __init__(self, device_port: DevicePort) -> None:
        self.device_port = device_port

    def __call__(self, plan: ExperimentPlan | Mapping[str, Any]) -> List[WellValidationResult]:
        try:
            if isinstance(plan, Mapping):
                domain_plan = build_experiment_plan(plan)
            elif isinstance(plan, ExperimentPlan):
                domain_plan = plan
            else:
                raise TypeError("ValidateStartPlan requires an ExperimentPlan or mapping input.")

            validations: List[WellValidationResult] = []
            for well_plan in domain_plan.wells:
                well_id_str = str(well_plan.well)
                if not well_id_str or len(well_id_str) < 2:
                    raise ValueError(f"Invalid well id '{well_id_str}'")
                box = well_id_str[0].upper()

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

                validations.append(
                    WellValidationResult(
                        well_id=WellId(well_id_str),
                        box_id=BoxId(box),
                        mode=mode,
                        ok=ok_flag and not errors,
                        errors=errors,
                        warnings=warnings,
                    )
                )
            return validations
        except UseCaseError:
            raise
        except Exception as exc:
            raise UseCaseError("VALIDATION_FAILED", str(exc))
