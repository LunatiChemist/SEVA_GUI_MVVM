from __future__ import annotations

import json
from pathlib import Path

from seva.adapters.storage_local import StorageLocal
from seva.viewmodels.settings_vm import (
    SettingsVM,
    default_settings_payload,
)


def test_apply_dict_updates_flat_keys() -> None:
    vm = SettingsVM()
    payload = {
        "results_dir": "./runs",
        "request_timeout_s": 12,
        "download_timeout_s": 34,
        "poll_interval_ms": 450,
        "poll_backoff_max_ms": 6000,
        "auto_download_on_complete": False,
        "api_base_urls": {"A": "https://example.test"},
        "api_keys": {"A": "secret-token"},
        "relay_ip": "192.168.0.2",
        "relay_port": 8080,
    }
    vm.apply_dict(payload)

    assert vm.results_dir == "./runs"
    assert vm.request_timeout_s == 12
    assert vm.download_timeout_s == 34
    assert vm.poll_interval_ms == 450
    assert vm.poll_backoff_max_ms == 6000
    assert vm.auto_download_on_complete is False
    assert vm.api_base_urls["A"] == "https://example.test"
    assert vm.api_keys["A"] == "secret-token"
    assert vm.relay_ip == "192.168.0.2"
    assert vm.relay_port == 8080


def test_storage_local_defaults_and_roundtrip(tmp_path: Path) -> None:
    storage = StorageLocal(root_dir=str(tmp_path))
    expected_defaults = default_settings_payload()
    assert storage.load_user_settings() == expected_defaults
    settings_path = tmp_path / "user_settings.json"
    assert not settings_path.exists()

    vm = SettingsVM()
    vm.apply_dict(
        {
            "results_dir": str(tmp_path / "results"),
            "request_timeout_s": 15,
            "download_timeout_s": 90,
            "poll_interval_ms": 300,
            "poll_backoff_max_ms": 9000,
            "auto_download_on_complete": True,
            "api_base_urls": {"A": "https://device.example"},
            "api_keys": {"A": "key-A"},
            "relay_ip": "10.0.0.5",
            "relay_port": 8123,
        }
    )
    payload = vm.to_dict()

    storage.save_user_settings(payload)
    assert settings_path.exists()
    assert list(tmp_path.glob("user_settings_*.tmp")) == []

    loaded = storage.load_user_settings()
    assert loaded == payload

    # Ensure saved JSON is valid and matches payload exactly
    with settings_path.open("r", encoding="utf-8") as fh:
        parsed = json.load(fh)
    assert parsed == payload
