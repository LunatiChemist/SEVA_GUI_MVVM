import json

from seva.adapters.storage_local import StorageLocal
from seva.viewmodels.settings_vm import SettingsVM


def test_user_settings_round_trip(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))
    payload = {
        "box_urls": {"A": "http://a"},
        "api_keys": {"A": "token"},
        "request_timeout_s": 5,
        "download_timeout_s": 15,
        "poll_interval_ms": 500,
        "results_dir": "/data/results",
        "use_streaming": True,
        "relay": {"ip": "10.0.0.1", "port": 9000},
        "debug_logging": True,
    }

    storage.save_user_settings(payload)
    loaded = storage.load_user_settings()

    assert loaded == payload


def test_user_settings_missing_file_and_save(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))
    settings_path = tmp_path / "user_settings.json"

    assert storage.load_user_settings() is None
    assert not settings_path.exists()

    vm = SettingsVM()
    storage.save_user_settings(vm.to_dict())

    assert settings_path.exists()
    with settings_path.open("r", encoding="utf-8") as fh:
        persisted = json.load(fh)

    assert persisted == vm.to_dict()


def test_settings_vm_apply_legacy_timeouts():
    vm = SettingsVM()
    payload = {
        "box_urls": {"A": "http://localhost"},
        "api_keys": {"A": "123"},
        "timeouts": {"request_s": 7, "download_s": 21},
        "poll_interval_ms": 600,
        "results_dir": "/tmp/out",
        "use_streaming": True,
        "relay": {"ip": "1.2.3.4", "port": 2222},
        "debug_logging": False,
    }

    vm.apply_dict(payload)

    assert vm.request_timeout_s == 7
    assert vm.download_timeout_s == 21
    assert vm.poll_interval_ms == 600
    assert vm.results_dir == "/tmp/out"
    assert vm.use_streaming is True
    assert vm.relay_ip == "1.2.3.4"
    assert vm.relay_port == 2222
    assert vm.debug_logging is False

    persisted = vm.to_dict()
    assert persisted["request_timeout_s"] == 7
    assert persisted["download_timeout_s"] == 21
    assert persisted["relay"]["ip"] == "1.2.3.4"
    assert persisted["relay"]["port"] == 2222
    assert persisted["debug_logging"] is False


def test_settings_vm_set_results_dir_strips_and_defaults():
    vm = SettingsVM()

    vm.set_results_dir("  /tmp/results  ")
    assert vm.results_dir == "/tmp/results"

    vm.set_results_dir("   ")
    assert vm.results_dir == "."

    vm.set_results_dir(None)  # type: ignore[arg-type]
    assert vm.results_dir == "."
