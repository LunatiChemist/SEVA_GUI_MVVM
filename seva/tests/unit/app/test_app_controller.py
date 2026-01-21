from __future__ import annotations

from seva.app.controller import AppController
from seva.viewmodels.settings_vm import SettingsVM


def test_controller_ensure_ready_wires_usecases() -> None:
    settings = SettingsVM()
    settings.api_base_urls = {"A": "http://box-a"}
    settings.api_keys = {"A": "token"}

    controller = AppController(settings)

    assert controller.ensure_ready() is True
    assert controller.job_adapter is not None
    assert controller.device_adapter is not None
    assert controller.uc_start is not None
    assert controller.uc_poll is not None
    assert controller.uc_download is not None
    assert controller.uc_cancel is not None
    assert controller.uc_test_connection is not None
