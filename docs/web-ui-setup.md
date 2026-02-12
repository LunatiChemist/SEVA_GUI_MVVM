# Web UI Setup (Vite + React)

This page covers the Web UI track that runs in a desktop browser and talks to the same REST API used by the Tkinter UI.

## Purpose

After setup, you can:

- Run SEVA in a browser (`web_ui/`) while keeping Tkinter available.
- Configure box URLs and API keys in browser-local settings.
- Import/export settings as JSON.
- Run start/poll/cancel/download flows across multiple boxes.
- Use discovery, firmware, NAS, and telemetry entrypoints from the Web UI.

## Prerequisites

- Node.js 20+ (Node 22 recommended for CI parity)
- npm
- A reachable REST API per box (see [REST API Setup Tutorial](rest-api-setup.md))

## Install and run locally

From repository root:

```bash
cd web_ui
npm install
npm run dev
```

Open the printed local URL (usually `http://localhost:5173`).

## Build locally

```bash
cd web_ui
npm run build
```

The production output is written to `web_ui/dist/`.

## Settings behavior

- Settings are saved to browser `localStorage` key `seva.web.settings.v1`.
- Use **Export JSON** to download a complete settings file.
- Use **Import JSON** to restore settings with schema validation.

Import failures are shown as technical errors and do not overwrite the current in-memory settings.

## Runtime flow

1. Open **Settings** and configure box base URLs.
2. Save settings to browser storage.
3. Open **Run Planner** and define one or more run entries (`wellId`, `boxId`, `slot`, `modes`, JSON params).
4. Validate mode payloads and start the run group.
5. Open **Run Monitor** for polling, cancel, and download actions.
6. Use **Diagnostics** for connection checks, discovery scans, firmware flash, device rescan/status, and NAS actions.
7. Use **Telemetry** for latest snapshot polling or SSE stream mode.

## GitHub Pages deployment path

The repository deploys both docs and web app to the same `gh-pages` branch:

- Docs under `/docs/`
- Web UI under `/app/`
- Root `/` contains links to both entrypoints

The workflow responsible is `.github/workflows/docs.yml`.

## CORS requirement

When serving the Web UI from GitHub Pages, the REST API must allow that origin via CORS:

- Set `CORS_ALLOW_ORIGINS` on each API host (comma-separated allowlist).
- Keep API on HTTPS when required by browser security/network policy.

See [REST API Setup Tutorial](rest-api-setup.md) for environment variable examples.
