from __future__ import annotations

import sys
import types
from unittest.mock import patch
from typing import Dict, Iterable, List

if "requests" not in sys.modules:
    class _RequestsSessionStub:
        def get(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP GET not supported in tests without requests")

        def post(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP POST not supported in tests without requests")

    class _RequestsExceptionsStub:
        Timeout = RuntimeError
        ConnectionError = RuntimeError
        RequestException = RuntimeError

    sys.modules["requests"] = types.SimpleNamespace(
        Session=_RequestsSessionStub,
        Response=object,
        exceptions=_RequestsExceptionsStub,
    )

from seva.app.main import App
from seva.domain.entities import GroupId


class _PlateStub:
    def __init__(self, configured: Iterable[str]) -> None:
        self._configured = list(configured)

    def configured(self) -> List[str]:
        return list(self._configured)


class _ExperimentStub:
    def __init__(self, params: Dict[str, Dict[str, str]]) -> None:
        self._params = params
        self.fields: Dict[str, str] = {}

    def build_well_params_map(self, configured: Iterable[str]) -> Dict[str, Dict[str, str]]:
        return {wid: self._params[wid] for wid in configured if wid in self._params}


class _SettingsStub:
    def __init__(self) -> None:
        self.results_dir = "results"
        self.experiment_name = "Experiment Alpha"
        self.subdir = "Batch-01"


def _app_stub() -> App:
    app = App.__new__(App)
    app.plate_vm = _PlateStub(["A1"])
    experiment_vm = _ExperimentStub(
        {
            "A1": {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.5",
                "cv.vertex2_v": "-0.5",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "1",
            }
        }
    )
    experiment_vm.fields["storage.client_datetime"] = "2024-03-05T10-15-30"
    app.experiment_vm = experiment_vm
    app.settings_vm = _SettingsStub()
    app._log = types.SimpleNamespace(debug=lambda *args, **kwargs: None)
    return app


def test_plan_includes_storage_metadata() -> None:
    app = _app_stub()

    with patch("seva.domain.plan_builder.make_group_id") as make_group_id:
        make_group_id.return_value = GroupId("grp-fixed")
        plan = app._build_domain_plan()

    assert plan.meta.experiment == "Experiment Alpha"
    assert plan.meta.subdir == "Batch-01"
    assert str(plan.meta.group_id) == "grp-fixed"
    expected_dt = app._parse_client_datetime_override(
        app.experiment_vm.fields["storage.client_datetime"]
    )
    assert plan.meta.client_dt.value == expected_dt

    wells = plan.wells
    assert len(wells) == 1
    assert str(wells[0].well) == "A1"
    assert plan.make_plot is False
    assert plan.tia_gain is None
    assert plan.sampling_interval is None
