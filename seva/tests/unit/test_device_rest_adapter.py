from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Optional, Sequence


if "requests" not in sys.modules:

    class _RequestsSessionStub:
        def get(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("requests Session stub not configured")

    sys.modules["requests"] = types.SimpleNamespace(Session=_RequestsSessionStub)

from seva.adapters.device_rest import DeviceRestAdapter
from seva.usecases.test_connection import TestConnection
from seva.domain.ports import BoxId, DevicePort


class _ResponseStub:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _SessionStub:
    def __init__(self, responses: Sequence[_ResponseStub]) -> None:
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []
        self._idx = 0

    def get(
        self,
        url: str,
        *,
        accept: str = "application/json",
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> _ResponseStub:
        hdrs = dict(headers or {})
        if accept and "Accept" not in hdrs:
            hdrs["Accept"] = accept
        self.calls.append({"url": url, "headers": hdrs, "timeout": timeout})
        if self._idx >= len(self._responses):
            raise RuntimeError("No stub response configured")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


def test_device_adapter_health_uses_health_endpoint() -> None:
    adapter = DeviceRestAdapter({"boxA": "http://box.local/api/"})
    stub = _SessionStub([_ResponseStub({"ok": True})])
    adapter.sessions["boxA"] = stub  # type: ignore[assignment]

    result = adapter.health("boxA")

    assert result == {"ok": True}
    assert stub.calls[0]["url"] == "http://box.local/api/health"
    assert stub.calls[0]["headers"]["Accept"] == "application/json"


def test_device_adapter_list_devices_filters_non_dict_entries() -> None:
    payload = [
        {"slot": "slot01", "port": "/dev/ttyUSB0"},
        "ignore-me",
        {"slot": "slot02"},
    ]
    adapter = DeviceRestAdapter({"boxB": "http://box.local"})
    stub = _SessionStub([_ResponseStub(payload)])
    adapter.sessions["boxB"] = stub  # type: ignore[assignment]

    devices = adapter.list_devices("boxB")

    assert stub.calls[0]["url"] == "http://box.local/devices"
    assert devices == [
        {"slot": "slot01", "port": "/dev/ttyUSB0"},
        {"slot": "slot02"},
    ]


def test_device_adapter_list_modes_normalizes_strings() -> None:
    payload = ["CV", {"mode": "CA", "label": "Chrono"}]
    adapter = DeviceRestAdapter({"boxC": "http://box"})
    stub = _SessionStub([_ResponseStub(payload)])
    adapter.sessions["boxC"] = stub  # type: ignore[assignment]

    modes = adapter.list_modes("boxC")

    assert modes == [{"mode": "CV"}, {"mode": "CA", "label": "Chrono"}]


def test_device_adapter_mode_params_raises_on_unauthorized() -> None:
    adapter = DeviceRestAdapter({"boxD": "http://box"})
    stub = _SessionStub([_ResponseStub("forbidden", status_code=401)])
    adapter.sessions["boxD"] = stub  # type: ignore[assignment]

    try:
        adapter.get_mode_params("boxD", "CV")
    except RuntimeError as exc:
        assert "HTTP 401" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unauthorized response")


def test_device_adapter_mode_params_raises_on_server_error() -> None:
    adapter = DeviceRestAdapter({"boxE": "http://box"})
    stub = _SessionStub([_ResponseStub("boom", status_code=503)])
    adapter.sessions["boxE"] = stub  # type: ignore[assignment]

    try:
        adapter.get_mode_params("boxE", "CV")
    except RuntimeError as exc:
        assert "HTTP 503" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for server error response")


class _DevicePortStub(DevicePort):
    def __init__(self, health_payload: Dict[str, Any], devices: List[Dict[str, Any]]) -> None:
        self._health_payload = health_payload
        self._devices = devices
        self.calls: List[Dict[str, Any]] = []

    def health(self, box_id: BoxId) -> Dict[str, Any]:
        self.calls.append({"method": "health", "box": box_id})
        return dict(self._health_payload)

    def list_devices(self, box_id: BoxId) -> List[Dict[str, Any]]:
        self.calls.append({"method": "list_devices", "box": box_id})
        return [dict(item) for item in self._devices]

    def list_modes(self, box_id: BoxId) -> List[Dict[str, Any]]:
        self.calls.append({"method": "list_modes", "box": box_id})
        return []

    def get_mode_params(self, box_id: BoxId, mode: str) -> Dict[str, Any]:
        self.calls.append({"method": "get_mode_params", "box": box_id, "mode": mode})
        return {}


def test_test_connection_usecase_uses_device_port() -> None:
    port = _DevicePortStub({"ok": False, "detail": "offline"}, [{"slot": "slot01"}])
    uc = TestConnection(device_port=port)

    result = uc("A")

    assert result["box_id"] == "A"
    assert result["health"]["devices"] == 1
    assert result["device_count"] == 1
    assert any(call["method"] == "health" for call in port.calls)
    assert any(call["method"] == "list_devices" for call in port.calls)
