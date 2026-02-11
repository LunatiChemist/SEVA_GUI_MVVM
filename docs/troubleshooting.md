# Troubleshooting

This page lists common issues when working with the GUI and the REST API, along
with quick fixes and where to look for logs.

For the full end-user workflow, see [GUI Overview & How to Use](gui_overview_how_to_use.md).

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

## Run does not start

Common causes:

- No wells selected in the Well Grid.
- Method checkboxes not enabled in the Experiment panel.
- Missing/invalid parameter values for enabled method sections.
- Connectivity issue on one or more configured boxes.

Quick checks:

1. Open **Settings** and run **Test** for each active box.
2. Confirm at least one well is selected.
3. Confirm at least one method (CV/DC-AC/Cdl/EIS) is enabled where required.
4. Try again with **Enable debug logging** turned on.

## Progress appears stuck

If progress does not update:

1. Verify network/API reachability again (`/health`).
2. Check if streaming is enabled but unsupported in your environment; toggle **Use streaming (SSE/WebSocket)**.
3. Increase polling interval/timeout values in **Settings → Timing** if your network is slow.
4. Watch server logs for long-running backend operations.

## Download did not appear

If runs complete but no files are visible:

1. Confirm **Results directory** in Settings points to a writable location.
2. If auto-download is disabled, use **Run Overview → Download Group** manually.
3. Check the **Runs** tab `Download Path` column.
4. Ensure local security software is not blocking folder creation.

## Downloads do not open the folder

Depending on OS policies, the "open folder" action might be blocked.

- **Windows**: ensure the Results directory exists and is writable.
- **Linux**: confirm that the default file manager is available for your desktop
  environment.
- If the folder does not open, manually navigate to the Results directory and
  verify files were downloaded.

## NAS setup: common problems (advanced/optional)

### NAS Health fails

- Verify NAS host/IP is reachable from the GUI machine.
- Verify SMB share name, username/password, and optional domain.
- Confirm firewall rules allow SMB traffic.
- Confirm API connection fields (Base URL/API key) are valid.

### Upload queue succeeds but files are missing on NAS

- Check `Base Subdir` and retention configuration for path expectations.
- Verify the run ID exists and has local downloaded data.
- Re-run a manual upload with a known-good run ID.

### Authentication errors

- Re-enter credentials carefully (including domain format if needed).
- Test SMB credentials outside the GUI if possible.
- Ensure account permission includes write access to the selected share.

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
