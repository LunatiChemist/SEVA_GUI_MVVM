from __future__ import annotations

from typing import List, Dict,Tuple

from ..domain.entities import ExperimentPlan
from ..domain.ports import BoxId, DevicePort, ModeValidationResult, UseCaseError, WellId, JobPort
from ..domain.util import normalize_mode_name, well_id_to_box
from .start_experiment_batch import WellValidationResult


class ValidateStartPlan:
    """Validate parameters and detect busy wells per box deterministically."""

    def __init__(self, device_port: DevicePort, job_port: JobPort) -> None:
        self.device_port = device_port
        self.job_port = job_port

    def __call__(self, plan: ExperimentPlan) -> List[WellValidationResult]:
        try:
            # key: (well_id_str, mode_str)  -> result
            per_well_mode: Dict[Tuple[str, str], WellValidationResult] = {}
            # key: box_id -> list[WellId] (für busy-check)
            wells_by_box: Dict[BoxId, List[WellId]] = {}

            for well_plan in plan.wells:
                well_id_str = str(well_plan.well)
                box = well_id_to_box(well_id_str)

                # Stelle sicher, dass wir später pro Box die betroffenen Wells kennen
                wells_by_box.setdefault(box, []).append(WellId(well_id_str))

                # Iteriere über alle Modi dieses Wells
                for mode_name in well_plan.modes:
                    raw_mode = str(mode_name)
                    mode_str = normalize_mode_name(raw_mode)
                    params = well_plan.params_by_mode[mode_str]

                    # Payload ableiten (gleiches Fehlermanagement wie zuvor)
                    try:
                        params_payload = params.to_payload()
                    except NotImplementedError as exc:
                        raise ValueError(
                            f"Well '{well_id_str}' mode '{mode_str}' parameters do not support payload serialization."
                        ) from exc
                    except AttributeError as exc:
                        raise ValueError(
                            f"Well '{well_id_str}' mode '{mode_str}' parameters are missing a to_payload() method."
                        ) from exc

                    # Modus bei der Device-API validieren
                    try:
                        result: ModeValidationResult = self.device_port.validate_mode(
                            box, mode_str, params_payload
                        )
                    except Exception as exc:
                        raise UseCaseError(
                            "VALIDATION_FAILED", f"{well_id_str}/{mode_str}: {exc}"
                        )

                    errors = list(result["errors"])
                    warnings = list(result["warnings"])
                    ok_flag = bool(result["ok"])

                    vr = WellValidationResult(
                        well_id=WellId(well_id_str),
                        box_id=BoxId(box),
                        mode=mode_str,
                        ok=ok_flag and not errors,
                        errors=errors,
                        warnings=warnings,
                    )
                    per_well_mode[(well_id_str, mode_str)] = vr

            # Busy-Check pro Box: markiert alle Modi eines busy Wells
            for box, bucket in wells_by_box.items():
                try:
                    busy = self.job_port.list_busy_wells(box)
                except Exception:
                    busy = (
                        set()
                    )  # als Warning zu behandeln wäre denkbar; bisher non-fatal
                if not busy:
                    continue

                for wid in bucket:
                    if str(wid) in busy:
                        # Alle Ergebnisse zu diesem Well anpassen (unabhängig vom Modus)
                        for (w_id, m_str), vr in per_well_mode.items():
                            if w_id == str(wid):
                                vr.ok = False
                                vr.errors.append("SLOT_BUSY")

            return list(per_well_mode.values())

        except UseCaseError:
            raise
        except Exception as exc:
            raise UseCaseError("VALIDATION_FAILED", str(exc))
