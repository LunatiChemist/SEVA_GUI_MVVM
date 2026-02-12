# NiceGUI Web Runtime

This guide documents the parallel NiceGUI runtime for SEVA.

## Purpose

The web runtime provides the same orchestration layers as Tkinter (ViewModels,
UseCases, and adapters) behind a browser UI.

Key points:

- Tkinter remains available (`python -m seva.app.main`).
- NiceGUI runs in parallel (`python -m seva.web_ui.main`).
- Settings persist in browser `localStorage` and support JSON import/export.

## Start the web runtime

From repository root:

```bash
python -m seva.web_ui.main --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

For a smoke check without starting the server:

```bash
python -m seva.web_ui.main --smoke-test
```

## Settings persistence

The `Settings` tab supports:

- Save to browser storage
- Load from browser storage
- Export settings JSON
- Import settings JSON

Imported payloads are applied through the existing `SettingsVM` compatibility
path (`SettingsVM.apply_dict`), so legacy payload keys remain loadable.

## Runtime tabs and workflows

- `Plate`: well selection and layout save/load actions.
- `Experiment`: CV/DCAC/CDL/EIS form editing, copy/paste, apply/reset.
- `Run Overview`: server-authoritative status projections.
- `Channel Activity`: device-status polling projection.
- `Runs`: active/history list, select/cancel/delete/download.
- `Settings`: 4-box URLs (A/B/C/D), timeouts, discovery, relay test.
- `Firmware`: firmware upload + flash workflow.
- `NAS`: setup/health/upload actions against selected box.
- `Data Plotter`: CSV upload and browser plotting.

## REST API web-friendliness

The REST API supports optional CORS configuration:

- Env var: `SEVA_CORS_ALLOW_ORIGINS`
- Value: comma-separated origins (for example `http://127.0.0.1:8080,http://localhost:8080`)

When unset, CORS middleware is not added.

## Deployment options

Current baseline is localhost/internal deployment. Provider choice is
deliberately open; run behind your preferred internal reverse proxy or process
manager after local validation.
