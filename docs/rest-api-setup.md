# REST API Setup Tutorial (Linux/Raspberry Pi)

This guide focuses on setting up and operating the FastAPI service in
`rest_api/`.

Use this page if you want to:

- install a fresh REST API environment,
- configure runtime variables safely,
- run health checks before connecting the GUI,
- and run the API as a persistent systemd autostart service.

## 1) Platform and prerequisites

Recommended target: Linux/Raspberry Pi.

- Python >=3.10
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
- `CORS_ALLOW_ORIGINS` (optional): comma-separated browser origins allowed to call the API.
- `CORS_ALLOW_METHODS` (optional): comma-separated CORS allow-method list, default `GET,POST,OPTIONS`.
- `CORS_ALLOW_HEADERS` (optional): comma-separated CORS allow-header list, default `Authorization,Content-Type,X-API-Key`.
- `CORS_ALLOW_CREDENTIALS` (optional): `true/false`, default `false`.

### A) Variables for interactive terminal runs

```bash
export BOX_API_KEY="change-me"
export BOX_ID="lab-box-01"
export RUNS_ROOT="/opt/box/runs"
export NAS_CONFIG_PATH="/opt/box/nas_smb.json"
export CORS_ALLOW_ORIGINS="https://lunatichemist.github.io"
```

### B) Variables for systemd service runs (recommended)

Create an environment file that systemd can load:

```bash
sudo install -d -m 0755 /etc/seva
sudo tee /etc/seva/box-api.env >/dev/null <<'ENV'
BOX_API_KEY=change-me
BOX_ID=lab-box-01
RUNS_ROOT=/opt/box/runs
NAS_CONFIG_PATH=/opt/box/nas_smb.json
BOX_BUILD=dev
BOX_BUILD_ID=local
CORS_ALLOW_ORIGINS=https://lunatichemist.github.io
CORS_ALLOW_METHODS=GET,POST,OPTIONS
CORS_ALLOW_HEADERS=Authorization,Content-Type,X-API-Key
CORS_ALLOW_CREDENTIALS=false
ENV
sudo chmod 600 /etc/seva/box-api.env
```

`EnvironmentFile=` is the most reliable way to “send” environment variables to
systemd-managed services.

## 4) Start the REST API manually (foreground)

Run from the REST API directory:

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

Interactive OpenAPI docs are available at:

- `http://<host>:8000/docs`

## 5) Configure systemd autostart service

If you want the API to survive reboot and run automatically, create a systemd
unit.

### A) Create service file

```bash
sudo tee /etc/systemd/system/pybeep-box.service >/dev/null <<'UNIT'
[Unit]
Description=SEVA / pyBEEP Box REST API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=<REPOSITORY_PATH>/rest_api
EnvironmentFile=/etc/seva/box-api.env
ExecStart=<VENV_PATH>/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
```

Adjust `User`, `Group`, `WorkingDirectory`, and `ExecStart` paths to match your
installation. (Optional) Keep `User` and `Group` as `root` if you are unsure about your permissions.

### B) Enable and start autostart

```bash
sudo systemctl daemon-reload
sudo systemctl enable pybeep-box.service
sudo systemctl start pybeep-box.service
```

### C) Verify and inspect logs

```bash
sudo systemctl status pybeep-box.service --no-pager
sudo journalctl -u pybeep-box.service -f
```

### D) Update environment variables later

After editing `/etc/seva/box-api.env`, reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart pybeep-box.service
```

## 6) Smoke test after startup

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

If you use systemd with `EnvironmentFile=`, your shell may not have
`$BOX_API_KEY`. In that case, send the key explicitly:

```bash
curl -H "X-API-Key: change-me" http://localhost:8000/health
```

Browser CORS preflight check (for GitHub Pages / Web UI):

```bash
curl -i -X OPTIONS "http://localhost:8000/health" \
  -H "Origin: https://lunatichemist.github.io" \
  -H "Access-Control-Request-Method: GET"
```

Expected when `CORS_ALLOW_ORIGINS` contains the origin:

- `access-control-allow-origin: https://lunatichemist.github.io` in response headers.

## 7) Restarting the REST API

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

## 8) Optional NAS/SMB setup check (Linux)

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

## 9) Related docs

- [Development Setup](dev-setup.md) for overall GUI + API onboarding.
- [REST API Workflows](workflows_rest_api.md) for end-to-end request flows.
- [Troubleshooting](troubleshooting.md) for common issues and logging tips.
