from __future__ import annotations

import json

import pytest

from seva.viewmodels.settings_vm import SettingsVM
from seva.web_ui.plotter_vm import WebPlotterVM
from seva.web_ui.viewmodels import WebSettingsVM, parse_settings_json


def test_web_settings_vm_roundtrip() -> None:
    payload = {
        "api_base_urls": {"A": "http://a:8000", "B": "http://b:8000", "C": "", "D": ""},
        "api_keys": {"A": "k1", "B": "k2", "C": "", "D": ""},
        "request_timeout_s": 12,
        "download_timeout_s": 90,
        "poll_interval_ms": 800,
        "poll_backoff_max_ms": 6000,
        "results_dir": "C:/results",
        "auto_download_on_complete": False,
        "experiment_name": "Exp1",
        "subdir": "SubA",
        "use_streaming": True,
        "debug_logging": True,
        "relay_ip": "10.0.0.10",
        "relay_port": 502,
        "firmware_path": "firmware.bin",
    }
    web_vm = WebSettingsVM.from_payload(payload)
    assert web_vm.api_base_urls["A"] == "http://a:8000"
    assert web_vm.request_timeout_s == 12
    settings_vm = SettingsVM()
    web_vm.apply_to_settings_vm(settings_vm)
    assert settings_vm.api_base_urls["B"] == "http://b:8000"
    assert settings_vm.relay_port == 502


def test_parse_settings_json_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        parse_settings_json(json.dumps(["not", "an", "object"]))


def test_plotter_vm_parses_csv_and_builds_options() -> None:
    content = b"time,current,voltage\n0,1.0,2.0\n1,1.5,2.2\n2,1.7,2.4\n"
    vm = WebPlotterVM()
    vm.load_csv_bytes(content, filename="sample.csv")
    assert vm.x_column == "time"
    assert vm.y_column == "current"
    options = vm.chart_options()
    assert options["xAxis"]["name"] == "time"
    assert len(options["series"]) >= 1
