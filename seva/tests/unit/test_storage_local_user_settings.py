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


def test_settings_vm_set_results_dir_strips_and_defaults():
    vm = SettingsVM()

    vm.set_results_dir("  /tmp/results  ")
    assert vm.results_dir == "/tmp/results"

    vm.set_results_dir("   ")
    assert vm.results_dir == "."

    vm.set_results_dir(None)  # type: ignore[arg-type]
    assert vm.results_dir == "."
