# SEVA GUI MVVM

## How to Run
- Use Python 3.11 and install dependencies via `pip install -e .` from the repo root.
- Start the FastAPI backend if you need live devices: `uvicorn app:app --host 0.0.0.0 --port 8000 --reload`.
- Launch the desktop client with `python -m seva.app.main`.

### Storage & Start-Flow
- Settings & layouts: JSON only (`user_settings.json`, layout exports). Remove any legacy CSV files before running.
- Configure `user_settings.json` (or the Settings dialog) so `results_dir`, `experiment_name`, and optional `subdir` are set before starting.
- Start-Flow plans carry `experiment_name`, optional `subdir`, and `client_datetime`; the server builds storage paths from these values (S7 contract).
