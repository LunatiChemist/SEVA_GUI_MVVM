from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Optional


if "requests" not in sys.modules:

    class _RequestsSessionStub:
        def get(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("requests Session stub not configured")

        def post(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("requests Session stub not configured")

    sys.modules["requests"] = types.SimpleNamespace(Session=_RequestsSessionStub)

from seva.adapters.job_rest import JobRestAdapter
from seva.adapters.job_rest_mock import JobRestMock
from seva.usecases.test_connection import TestConnection


class _ResponseStub:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _SessionStub:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        timeout: Optional[int] = None,
        stream: bool = False,
    ) -> _ResponseStub:
        self.calls.append({"url": url, "accept": accept, "timeout": timeout})
        return _ResponseStub(self.payload)


def test_job_rest_adapter_health_uses_health_endpoint() -> None:
    adapter = JobRestAdapter({"boxA": "http://box.local/api/"})
    stub = _SessionStub({"ok": True, "devices": 3})
    adapter.sessions["boxA"] = stub

    result = adapter.health("boxA")

    assert result == {"ok": True, "devices": 3}
    assert stub.calls[0]["url"] == "http://box.local/api/health"
    assert stub.calls[0]["accept"] == "application/json"


def test_job_rest_adapter_list_devices_filters_non_dict() -> None:
    adapter = JobRestAdapter({"boxB": "http://box.local"})
    payload = [{"slot": "slot01", "port": "/dev/tty0"}, "invalid", {"slot": "slot02"}]
    stub = _SessionStub(payload)
    adapter.sessions["boxB"] = stub

    devices = adapter.list_devices("boxB")

    assert stub.calls[0]["url"] == "http://box.local/devices"
    assert devices == [
        {"slot": "slot01", "port": "/dev/tty0"},
        {"slot": "slot02"},
    ]


def test_job_rest_mock_static_responses() -> None:
    mock = JobRestMock(
        health_status={"A": {"ok": False, "message": "offline"}},
        devices={"A": [{"slot": "slot01", "port": "/dev/ttyACM0"}]},
    )

    health = mock.health("A")
    devices = mock.list_devices("A")

    assert health["ok"] is False
    assert health["devices"] == 1
    assert health["message"] == "offline"
    assert devices == [{"slot": "slot01", "port": "/dev/ttyACM0"}]


def test_test_connection_usecase_combines_health_and_devices() -> None:
    mock = JobRestMock(
        health_status={"B": {"ok": True}},
        devices={"B": [{"slot": "slot03", "port": "/dev/ttyUSB1"}]},
    )
    uc = TestConnection(job_port=mock)

    result = uc("B")

    assert result["box_id"] == "B"
    assert result["ok"] is True
    assert result["health"]["devices"] == 1
    assert result["device_count"] == 1
    assert result["devices"][0]["slot"] == "slot03"
