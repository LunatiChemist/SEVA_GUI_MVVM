from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..domain.ports import DevicePort, UseCaseError, WellId
from .start_experiment_batch import (
    WellValidationResult,
    _derive_mode,
    _normalize_params,
)


def _issue_list(raw: Any) -> List[Dict[str, Any]]:
    """Filter payload issue entries to dict objects."""
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


class ValidateStartPlan:
    """Run device-side validation for each well in the supplied plan."""

    def __init__(self, device_port: DevicePort) -> None:
        self.device_port = device_port

    def __call__(self, plan: Dict[str, Any]) -> List[WellValidationResult]:
        try:
            selection: Iterable[str] = plan.get("selection") or []
            selection = list(selection)
            if not selection:
                raise ValueError("Start plan has no wells (selection is empty).")

            well_params_map: Dict[str, Dict[str, Any]] = plan.get("well_params_map") or {}
            if not well_params_map:
                raise ValueError(
                    "Start plan has no per-well parameters (well_params_map missing)."
                )

            validations: List[WellValidationResult] = []
            for well_id in selection:
                if not well_id or len(well_id) < 2:
                    raise ValueError(f"Invalid well id '{well_id}'")
                box = well_id[0].upper()
                snapshot = well_params_map.get(well_id)
                if not snapshot:
                    raise ValueError(f"No saved parameters for well '{well_id}'")

                mode = _derive_mode(snapshot)
                params = _normalize_params(mode, snapshot)

                try:
                    payload = self.device_port.validate_mode(box, mode, params)
                except Exception as exc:
                    raise UseCaseError("VALIDATION_FAILED", f"{well_id}: {exc}")

                errors = _issue_list(payload.get("errors"))
                warnings = _issue_list(payload.get("warnings"))

                ok_flag = bool(payload.get("ok"))
                if payload.get("ok") is None and not errors:
                    ok_flag = True

                validations.append(
                    WellValidationResult(
                        well_id=WellId(str(well_id)),
                        box_id=box,
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
