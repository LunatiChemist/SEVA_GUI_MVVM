# SEVA GUI MVVM — Electrochemistry Client & Pi Box API

SEVA is a desktop GUI (Tkinter) plus a Raspberry-Pi-hosted FastAPI backend for
running electrochemical experiments on one or more boxes.

The codebase follows **MVVM + Hexagonal architecture**:

- **Views** render UI only.
- **ViewModels** hold UI state and commands.
- **UseCases** orchestrate business workflows (start, poll, cancel, download).
- **Adapters** handle external I/O (HTTP, filesystem, NAS, relay, firmware).

## Quick start

### GUI (Windows/Linux/macOS)

```bash
pip install -r requirements.txt
python -m seva.app.main
```

### REST API (Linux/Raspberry Pi)

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Where to go next

- Project docs home: `docs/index.md`
- Development setup: `docs/dev-setup.md`
- REST API setup: `docs/rest-api-setup.md`
- Architecture overview: `docs/architecture_overview.md`
- GUI workflows: `docs/workflows_seva.md`
- REST workflows: `docs/workflows_rest_api.md`
- GUI user tutorial: `docs/gui_overview_how_to_use.md`

## Reproducible dependencies

`requirements.txt` references `pyBEEP` via Git URL. For offline installations,
use the vendored copy in `vendor/pyBEEP` and document the local install path in
deployment procedures.

## License

MIT
