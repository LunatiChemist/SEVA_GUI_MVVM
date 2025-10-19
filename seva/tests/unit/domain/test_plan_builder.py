from __future__ import annotations

from datetime import datetime
from typing import Dict
from unittest.mock import patch

from seva.domain.entities import GroupId
from seva.domain.plan_builder import build_meta, from_well_params
from seva.domain.params import CVParams


def _cv_snapshot() -> Dict[str, str]:
    return {
        "run_cv": "1",
        "cv.start_v": "",
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.5",
        "cv.final_v": "0",
        "cv.scan_rate_v_s": "0.1",
        "cv.cycles": "2",
    }


def test_build_meta_trims_fields_and_generates_group_id() -> None:
    captured = {}

    def _fake_make_group_id(meta):
        captured["meta"] = meta
        return GroupId("grp-TEST")

    naive_dt = datetime(2025, 1, 2, 3, 4, 5)
    with patch("seva.domain.plan_builder.make_group_id", side_effect=_fake_make_group_id):
        meta = build_meta(" Experiment  ", "  Subdir  ", naive_dt)

    assert meta.experiment == "Experiment"
    assert meta.subdir == "Subdir"
    assert str(meta.group_id) == "grp-TEST"
    assert meta.client_dt.value.tzinfo is not None

    captured_meta = captured["meta"]
    assert captured_meta.experiment == "Experiment"
    assert captured_meta.subdir == "Subdir"


def test_from_well_params_builds_experiment_plan() -> None:
    with patch("seva.domain.plan_builder.make_group_id", return_value=GroupId("grp-1234")):
        meta = build_meta("Exp", None, datetime(2025, 1, 2, 3, 4, 5))

    plan = from_well_params(
        meta=meta,
        well_params_map={"A1": _cv_snapshot()},
        make_plot=True,
        tia_gain=None,
        sampling_interval=None,
    )

    assert plan.meta is meta
    assert plan.make_plot is True
    assert len(plan.wells) == 1

    well_plan = plan.wells[0]
    assert str(well_plan.well) == "A1"
    assert str(well_plan.mode) == "CV"
    assert isinstance(well_plan.params, CVParams)
    payload = well_plan.params.to_payload()
    assert payload["start"] == 0.0
    assert payload["vertex1"] == 0.5
    assert payload["vertex2"] == -0.5
