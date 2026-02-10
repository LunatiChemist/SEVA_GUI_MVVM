# REST API Setup Tutorial (Linux/Raspberry Pi)

This guide focuses on setting up and operating the FastAPI service in
`rest_api/`.

Use this page if you want to:

- install a fresh REST API environment,
- configure runtime variables safely,
- run health checks before connecting the GUI,
- and restart the API cleanly after changes.

## 1) Platform and prerequisites

Recommended target: Linux/Raspberry Pi.

- Python 3.10–3.12
- Git
- Network access for dependency install (or a prepared offline wheelhouse)

For NAS/SMB workflows, Linux system tools are also required:

- `mount` with CIFS support (`cifs-utils` package on many distros)
- `rsync`

## 2) Install dependencies

From repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### Reproducible pyBEEP installs (offline/vendor note)

`requirements.txt` currently pins pyBEEP from a Git URL. For environments
without internet access, vendor pyBEEP in-repo and install it from a local
path (the file already contains a commented local editable example).

## 3) Configure environment variables

The API reads configuration from environment variables at startup.

- `BOX_API_KEY` (optional): if set, every protected request must send
  `X-API-Key`.
- `BOX_ID` (optional): identifier returned by `/health`.
- `RUNS_ROOT` (optional): run output root directory, default `/opt/box/runs`.
- `NAS_CONFIG_PATH` (optional): SMB config path,
  default `/opt/box/nas_smb.json`.
- `BOX_BUILD` / `BOX_BUILD_ID` (optional): build metadata for `/version`.

Example:

```bash
export BOX_API_KEY="change-me"
export BOX_ID="lab-box-01"
export RUNS_ROOT="/opt/box/runs"
export NAS_CONFIG_PATH="/opt/box/nas_smb.json"
```

## 4) Start the REST API

Run from the REST API directory:

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

Interactive OpenAPI docs are available at:

- `http://<host>:8000/docs`

## 5) Smoke test after startup

Use these checks before connecting the GUI.

Without API key:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/devices
curl http://localhost:8000/modes
```

With API key:

```bash
curl -H "X-API-Key: $BOX_API_KEY" http://localhost:8000/health
curl -H "X-API-Key: $BOX_API_KEY" http://localhost:8000/devices
curl -H "X-API-Key: $BOX_API_KEY" http://localhost:8000/modes
```

## 6) Restarting the REST API

### A) If running in a terminal

1. Stop the server with `Ctrl+C`.
2. Ensure your virtualenv/environment variables are still active.
3. Start again:

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

### B) If running as a `systemd` service

```bash
sudo systemctl restart pybeep-box.service
sudo systemctl status pybeep-box.service --no-pager
```

Optional live logs:

```bash
sudo journalctl -u pybeep-box.service -f
```

## 7) Optional NAS/SMB setup check (Linux)

Configure once:

```bash
curl -X POST http://localhost:8000/nas/setup \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOX_API_KEY" \
  -d '{
        "host": "nas.local",
        "share": "experiments",
        "username": "lab",
        "password": "***",
        "base_subdir": "projectA/line2",
        "retention_days": 14
      }'
```

Check connectivity:

```bash
curl -H "X-API-Key: $BOX_API_KEY" http://localhost:8000/nas/health
```

## 8) Related docs

- [Development Setup](dev-setup.md) for overall GUI + API onboarding.
- [REST API Workflows](workflows_rest_api.md) for end-to-end request flows.
- [Troubleshooting](troubleshooting.md) for common issues and logging tips.
