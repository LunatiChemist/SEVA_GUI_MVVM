from seva.adapters.storage_local import StorageLocal


def test_save_and_load_user_settings_round_trip(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))
    payload = {
        "box_urls": {"A": "http://localhost:8000", "B": ""},
        "api_keys": {"A": "secret", "B": ""},
        "request_timeout_s": 15,
        "download_timeout_s": 45,
        "results_dir": "/tmp/results",
        "use_streaming": True,
        "relay": {"ip": "127.0.0.1", "port": 9000},
    }

    storage.save_user_settings(payload)
    loaded = storage.load_user_settings()

    assert loaded == payload


def test_load_user_settings_missing_file_returns_none(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))

    loaded = storage.load_user_settings()

    assert loaded is None
