# Troubleshooting

This page lists common issues when working with the GUI and the REST API, along
with quick fixes and where to look for logs.

## Nothing discovered

If device discovery returns nothing:

1. Verify the REST API is running on the target device.
2. In the GUI **Settings**, confirm the base URL/IP and port are correct.
3. Use **Test Connection** to verify `/health` and `/devices` respond.
4. On the Pi, ensure devices are attached and recognized by the OS.

## Wrong base URL / API not reachable

Symptoms: errors on startup, failed polls, or "connection refused".

- Check the GUI **Settings** → API base URL/IP for each box.
- Confirm the API is reachable from the GUI host:

```bash
curl http://<box-ip>:8000/health
```

## Downloads do not open the folder

Depending on OS policies, the "open folder" action might be blocked.

- **Windows**: ensure the Results directory exists and is writable.
- **Linux**: confirm that the default file manager is available for your desktop
  environment.
- If the folder does not open, manually navigate to the Results directory and
  verify files were downloaded.

## Logging & debug output

### GUI debug logging

Enable **Settings → Enable debug logging** to increase verbosity for the GUI.

You can also force logging levels via environment variables:

- `SEVA_LOG_LEVEL` / `SEVA_GUI_LOG_LEVEL` (explicit level like `DEBUG`)
- `SEVA_DEBUG_LOGGING` / `SEVA_GUI_DEBUG` / `SEVA_DEBUG` (truthy → DEBUG)

### REST API logging

Use `uvicorn` with the default logging output or increase verbosity via:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --log-level debug
```

If you need more detail, check the system logs on the Pi host.
