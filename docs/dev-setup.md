# Development Setup

This guide focuses on developers who are familiar with Python but new to the SEVA
codebase. It covers both UI tracks (Tkinter and Web UI) plus the REST API.

## Prerequisites

- Python 3.10-3.12
- Git
- Node.js 20+ and npm (for `web_ui/`)

## Install Python dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

## Run the Tkinter GUI (Windows/Linux)

Start the desktop GUI locally with:

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

## Run the Web UI (desktop browser)

From repository root:

```bash
cd web_ui
npm install
npm run dev
```

Build production assets:

```bash
cd web_ui
npm run build
```

For Web UI workflow and deployment details, see:

- **[Web UI Setup](web-ui-setup.md)**

## Run the REST API (Linux/Raspberry Pi)

The REST API is intended to run on Linux/Raspberry Pi devices. On the Pi (or
Linux host), start the FastAPI app from the directory where `rest_api/app.py`
lives:

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

For a full setup tutorial (installation, env vars, smoke tests, NAS/SMB checks,
and restart procedures), see:

- **[REST API Setup Tutorial](rest-api-setup.md)**

### REST API environment variables (quick reference)

- `RUNS_ROOT`: Root directory where run data is stored. Default `/opt/box/runs`.
- `BOX_API_KEY`: Optional API key for securing requests.
- `BOX_ID`: Identifier for the box (used in health/device responses).
- `NAS_CONFIG_PATH`: Optional path for NAS/SMB configuration persistence.
- `BOX_BUILD` / `BOX_BUILD_ID`: Optional build metadata for versioning.
- `CORS_ALLOW_ORIGINS`: Optional comma-separated browser origin allowlist.

Example:

```bash
RUNS_ROOT="/opt/box/runs" BOX_ID="A" uvicorn app:app --host 0.0.0.0 --port 8000
```

## Next steps

- Review the **Architecture Overview** for MVVM + Hexagonal boundaries.
- Use **SEVA GUI workflows** and **REST API workflows** to navigate use cases.
- Check **Troubleshooting** for common issues.
