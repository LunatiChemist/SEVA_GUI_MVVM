# Development Setup

This guide focuses on developers who are familiar with Python but new to the SEVA
codebase. It covers setting up the GUI (Windows/Linux) and running the REST API
on Linux/Raspberry Pi.

## Prerequisites

- Python 3.10–3.12
- Git

## Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

## Run the GUI (Windows/Linux)

Start the Tkinter GUI locally with:

```bash
python -m seva.app.main
```

If you need a custom storage root (where the GUI reads/writes local files), set
`SEVA_STORAGE_ROOT` before starting:

```bash
SEVA_STORAGE_ROOT="path/to/storage" python -m seva.app.main
```

On Windows (PowerShell):

```powershell
$env:SEVA_STORAGE_ROOT="path\\to\\storage"
python -m seva.app.main
```

## Run the REST API (Linux/Raspberry Pi)

The REST API is intended to run on Linux/Raspberry Pi devices. On the Pi (or
Linux host), start the FastAPI app from the directory where `rest_api/app.py`
lives:

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

### REST API environment variables

You can customize the API with these environment variables:

- `RUNS_ROOT`: Root directory where run data is stored. Defaults to `/opt/box/runs`.
- `BOX_API_KEY`: Optional API key for securing requests.
- `BOX_ID`: Identifier for the box (used in health/device responses).
- `BOX_BUILD` / `BOX_BUILD_ID`: Optional build metadata for versioning.

Example:

```bash
RUNS_ROOT="/opt/box/runs" BOX_ID="A" uvicorn app:app --host 0.0.0.0 --port 8000
```

## Next steps

- Review the **Architecture Overview** for MVVM + Hexagonal boundaries.
- Use **SEVA GUI workflows** and **REST API workflows** to navigate use cases.
- Check **Troubleshooting** for common issues.
