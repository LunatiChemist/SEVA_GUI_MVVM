# SEVA GUI MVVM — Electrochemistry Client & Pi Box API

SEVA is an end-user GUI for starting and monitoring HTE electrochemistry experiments on Matterlab potentiostats.
It supports multi-box operation, run monitoring, result downloads, and optional NAS-based workflows for lab data handling.

## What is SEVA?

SEVA combines a desktop GUI (Tkinter) with a Raspberry-Pi-hosted FastAPI backend for electrochemical run orchestration.
The repository now also includes a Web UI track (`web_ui/`) that runs in a desktop browser.

Key highlights:
- Start and monitor grouped experiments across one or more boxes.
- Configure CV, DC/AC, Cdl, and EIS workflows from the GUI.
- Track per-box and per-channel activity during runs.
- Download results and use the integrated data plotter for post-run analysis/export.
- Use optional NAS/SMB workflows for retention and upload scenarios.

## Quick start (deployment-first)

### Use the GUI (recommended)

```bash
pip install -r requirements.txt
python -m seva.app.main
```

### Use the Web UI

```bash
cd web_ui
npm install
npm run dev
```

### Run the REST API (Raspberry Pi / Linux)

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

If setup or runtime issues occur, use the troubleshooting guide:
- https://lunatichemist.github.io/SEVA_GUI_MVVM/troubleshooting/

## Documentation (hosted)

- Docs home: https://lunatichemist.github.io/SEVA_GUI_MVVM/
- GUI user tutorial: https://lunatichemist.github.io/SEVA_GUI_MVVM/gui_overview_how_to_use/
- Development setup: https://lunatichemist.github.io/SEVA_GUI_MVVM/dev-setup/
- Web UI setup: https://lunatichemist.github.io/SEVA_GUI_MVVM/web-ui-setup/
- REST API setup: https://lunatichemist.github.io/SEVA_GUI_MVVM/rest-api-setup/

For developers who need architecture, workflows, and deeper implementation details, see the full hosted docs index above.

## License

MIT
