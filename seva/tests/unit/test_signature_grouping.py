import pytest
from datetime import datetime

from seva.domain.plan_builder import build_meta, from_well_params


def _meta():
    return build_meta("Experiment", None, datetime(2025, 1, 1, 12, 0, 0))


def test_from_well_params_sets_cv_mode():
    plan = from_well_params(
        meta=_meta(),
        well_params_map={
            "A1": {
                "run_cv": "1",
                "cv.vertex1_v": "0.5",
                "cv.vertex2_v": "-0.5",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "1",
            }
        },
        make_plot=True,
        tia_gain=None,
        sampling_interval=None,
    )

    assert plan.wells[0].mode.value == "CV"



def test_from_well_params_raises_when_multiple_modes_enabled():
    with pytest.raises(ValueError):
        from_well_params(
            meta=_meta(),
            well_params_map={
                "A1": {"run_cv": "1", "run_dc": "1", "cv.vertex1_v": "0.5"}
            },
            make_plot=True,
            tia_gain=None,
            sampling_interval=None,
        )



def test_from_well_params_raises_for_unsupported_mode():
    with pytest.raises(NotImplementedError):
        from_well_params(
            meta=_meta(),
            well_params_map={"A1": {"run_dc": "1"}},
            make_plot=True,
            tia_gain=None,
            sampling_interval=None,
        )
