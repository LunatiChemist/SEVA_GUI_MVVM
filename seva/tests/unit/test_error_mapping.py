from __future__ import annotations

import logging
import sys
import types
from typing import List

if "requests" not in sys.modules:
    class _RequestsSessionStub:
        def get(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP GET not supported in tests without requests")

        def post(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP POST not supported in tests without requests")

    class _RequestException(Exception):
        pass

    class _Timeout(_RequestException):
        pass

    class _ConnectionError(_RequestException):
        pass

    requests_stub = types.ModuleType("requests")
    requests_stub.Session = _RequestsSessionStub
    requests_stub.Response = object
    requests_stub.exceptions = types.SimpleNamespace(
        Timeout=_Timeout,
        ConnectionError=_ConnectionError,
        RequestException=_RequestException,
    )
    sys.modules["requests"] = requests_stub

from seva.adapters.api_errors import ApiClientError, ApiServerError, ApiTimeoutError
from seva.app.main import App


class _ToastRecorder:
    def __init__(self) -> None:
        self.messages: List[str] = []

    def show_toast(self, message: str) -> None:
        self.messages.append(message)


def _app_for_tests() -> App:
    app = App.__new__(App)
    app.win = _ToastRecorder()
    app._log = logging.getLogger("test.app")
    return app


def test_toast_invalid_parameters_uses_hint() -> None:
    app = _app_for_tests()
    err = ApiClientError("ctx", status=422, hint="A1: voltage missing")

    app._toast_error(err)

    assert app.win.messages[-1] == "Invalid parameters: A1: voltage missing"


def test_toast_slot_busy_includes_slot_and_context() -> None:
    app = _app_for_tests()
    err = ApiClientError("ctx", status=409, payload={"slot": "slot05"})

    app._toast_error(err, context="Box B")

    assert app.win.messages[-1] == "Box B: Slot busy: slot05"


def test_toast_auth_failure() -> None:
    app = _app_for_tests()
    err = ApiClientError("ctx", status=401)

    app._toast_error(err)

    assert app.win.messages[-1] == "Auth failed / API key invalid."


def test_toast_server_error() -> None:
    app = _app_for_tests()
    err = ApiServerError("ctx", status=500)

    app._toast_error(err)

    assert app.win.messages[-1] == "Box error, try again."


def test_toast_timeout() -> None:
    app = _app_for_tests()
    err = ApiTimeoutError("timeout", context="GET http://box")

    app._toast_error(err)

    assert app.win.messages[-1] == "Request timed out. Check connection."
