"""Contract-focused tests for box version refresh use case."""

from __future__ import annotations

import pytest

from seva.domain.ports import UseCaseError
from seva.usecases.refresh_box_versions import RefreshBoxVersions


class FakeDevicePort:
    """Simple fake port for version/health refresh tests."""

    def __init__(self) -> None:
        self.version_calls: list[str] = []
        self.health_calls: list[str] = []

    def version(self, box_id: str):
        self.version_calls.append(box_id)
        if box_id == "B":
            raise RuntimeError("down")
        return {
            "api": "1.2.3",
            "pybeep": "0.9.1",
            "firmware": "1.0.0",
            "python": "3.13.0",
            "build": "build-42",
        }

    def health(self, box_id: str):
        self.health_calls.append(box_id)
        return {"ok": True, "devices": 8, "box_id": f"BOX-{box_id}"}


def test_refresh_box_versions_collects_infos_and_failures() -> None:
    port = FakeDevicePort()
    uc = RefreshBoxVersions(port)

    result = uc(box_ids=["A", "B"])

    assert set(result.infos.keys()) == {"A"}
    assert "B" in result.failures
    assert result.infos["A"].api_version == "1.2.3"
    assert result.infos["A"].firmware_version == "1.0.0"
    assert result.infos["A"].reported_box_id == "BOX-A"
    assert result.infos["A"].health_devices == 8
    assert port.version_calls == ["A", "B"]
    assert port.health_calls == ["A"]


def test_refresh_box_versions_requires_box_ids() -> None:
    uc = RefreshBoxVersions(FakeDevicePort())
    with pytest.raises(UseCaseError) as excinfo:
        uc(box_ids=[])
    assert excinfo.value.code == "VERSION_NO_TARGETS"
