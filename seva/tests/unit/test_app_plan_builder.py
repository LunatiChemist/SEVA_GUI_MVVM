from __future__ import annotations

import sys
import types
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


class _PlateStub:
    def __init__(self, configured: Iterable[str]) -> None:
        self._configured = list(configured)

    def configured(self) -> List[str]:
        return list(self._configured)


class _ExperimentStub:
    def __init__(self, params: Dict[str, Dict[str, str]]) -> None:
        self._params = params

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
    app.experiment_vm = _ExperimentStub({"A1": {"run_cv": "1"}})
    app.settings_vm = _SettingsStub()
    app._current_client_datetime = lambda: "2024-03-05T10:15:30Z"  # type: ignore[method-assign]
    app._log = types.SimpleNamespace(debug=lambda *args, **kwargs: None)
    return app


def test_plan_includes_storage_metadata() -> None:
    app = _app_stub()

    plan = app._build_plan_from_vm(["A1"])

    assert plan["selection"] == ["A1"]
    assert plan["well_params_map"] == {"A1": {"run_cv": "1"}}
    assert plan["storage"]["experiment_name"] == "Experiment Alpha"
    assert plan["storage"]["subdir"] == "Batch-01"
    assert plan["storage"]["client_datetime"] == "2024-03-05T10:15:30Z"
    assert plan["storage"]["results_dir"] == "results"
