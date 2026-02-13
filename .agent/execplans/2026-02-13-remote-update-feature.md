# Remote-Update-Feature für REST API + GUI Settings

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Diese Planung wird gemäß `.agent/PLANS.md` geführt und muss während der Umsetzung laufend aktualisiert werden.

## Purpose / Big Picture

Nach dieser Änderung kann ein User in den Settings der GUI ein einziges Update-ZIP auswählen und remote an eine Box (Raspberry Pi mit `rest_api`) senden. Die Box entpackt das Archiv, validiert ein festes Manifest und führt dann gezielt Teil-Updates aus: REST API, pyBEEP (`.vendor`) und optional Firmware-Image-Vorbereitung. Der eigentliche Firmware-Flash bleibt weiterhin ein separater Endpoint/Schritt, wie gefordert.

User-sichtbar bedeutet das:

- Ein neuer „Gesamt-Update“-Flow ersetzt im Settings-Dialog den bisherigen „nur Firmware“-Flow.
- Ein standardisiertes ZIP-Format stellt sicher, dass API und Raspberry Pi sich auf Struktur, Versionen und Prüfsummen verlassen können.
- Der User bekommt pro Komponente ein klares Ergebnis (angewendet/übersprungen/fehlgeschlagen) plus konkrete Fehlercodes.
- Versionen von API, pyBEEP und Geräte-Firmware sind gezielt einsehbar.

## Progress

- [x] (2026-02-13 00:00Z) Ist-Zustand in `rest_api/`, `seva/` und `docs/` geprüft (Firmware-Flow, Version-Endpoint, Settings-Integration).
- [x] (2026-02-13 00:00Z) Zielbild für ZIP-Struktur, API-Endpoint, Ausführungsreihenfolge, Rückgabeformat und Version-Checks definiert.
- [ ] ExecPlan in Implementierungs-Milestones umsetzen (API, UseCases, Adapter, GUI, Tests, Doku).
- [ ] Legacy-„nur Firmware“-UI-Pfad entfernen und vollständig durch Gesamt-Update ersetzen.

## Surprises & Discoveries

- Observation: Die API liefert bereits `/version` mit `api`, `pybeep`, `python`, `build`; es fehlt nur noch ein strukturierter Geräte-Firmware-Stand.
  Evidence: `rest_api/app.py` enthält `version_info()` und `PYBEEP_VERSION`-Ermittlung.

- Observation: Der aktuelle GUI-Settings-Flow ist auf lokale `.bin`-Datei + `POST /firmware/flash` ausgelegt und in Controller/View eng verbunden.
  Evidence: `seva/app/settings_controller.py` (`handle_browse_firmware`, `handle_flash_firmware`) und `seva/app/views/settings_dialog.py` (Firmware-Group).

- Observation: Architekturgrenzen sind bereits gut vorbereitet: UseCase-orchestriert, Adapter für Transport, View nur UI.
  Evidence: `seva/usecases/flash_firmware.py`, `seva/adapters/firmware_rest.py`, `docs/workflows_seva.md`.

## Decision Log

- Decision: ZIP bekommt ein verpflichtendes Manifest (`manifest.json`) als Single Source of Truth für Inhalte, Zielpfade und Prüfsummen.
  Rationale: Frühe Validierung, robuste Fehlercodes, keine impliziten Dateinamen-Heuristiken.
  Date/Author: 2026-02-13 / Codex

- Decision: Firmware-Flash bleibt separater Endpoint (`/firmware/flash`). Gesamt-Update darf Firmware-Binary nur bereitstellen/ablegen und als „pending_flash“ markieren.
  Rationale: Entspricht Benutzeranforderung und trennt riskanten Hardware-Flash von Paketdeployment.
  Date/Author: 2026-02-13 / Codex

- Decision: API-seitig wird ein asynchroner Job-Endpoint für Gesamt-Updates eingeführt (`start -> poll`), statt langer synchroner Upload-Request.
  Rationale: Große ZIPs + Entpacken + Dateikopie können länger dauern; GUI braucht Polling-kompatiblen Fortschritt.
  Date/Author: 2026-02-13 / Codex

- Decision: GUI ersetzt bestehenden Firmware-Block durch „Remote Update“-Block; separater Button „Firmware jetzt flashen“ bleibt als Folgeschritt sichtbar.
  Rationale: Bestehender Nutzer-Workflow bleibt verständlich, gleichzeitig wird Gesamt-Update zentralisiert.
  Date/Author: 2026-02-13 / Codex

## Outcomes & Retrospective

Noch offen (Planungsstand). Erwartetes Ergebnis nach Umsetzung:

- Einheitliches Paketformat mit validierbarem Manifest.
- Ein konsistenter End-to-End-Updateflow über MVVM + Hexagonal Grenzen.
- Verbesserte Transparenz durch strukturierte Statusrückgaben und Versionsendpoints.

## Context and Orientation

Aktueller Stand in diesem Repository:

- `rest_api/app.py` hat bereits:
  - `POST /firmware/flash` (Upload `.bin`, dann Flash via `auto_flash_linux.py`),
  - `GET /version` mit API/pyBEEP/Python/Build,
  - keine Gesamt-Update-Route.
- GUI Settings haben bereits Firmware-Upload-UI:
  - View: `seva/app/views/settings_dialog.py` (Firmware-Datei + Flash-Button)
  - Controller: `seva/app/settings_controller.py` (Datei wählen, UseCase triggern)
  - UseCase: `seva/usecases/flash_firmware.py`
  - Adapter: `seva/adapters/firmware_rest.py`
- Architektur-Regeln (MVVM + Hexagonal) und Workflows sind dokumentiert in:
  - `docs/workflows_rest_api.md`
  - `docs/workflows_seva.md`
  - `docs/classes_rest_api.md`
  - `docs/classes_seva.md`

Begriffe in diesem Plan:

- „Manifest“: JSON-Datei im ZIP, die Versionsinfos, enthaltene Komponenten, Prüfsummen und Update-Policy enthält.
- „Staging“: temporäres Ablegen und Entpacken eines Uploads in einem Arbeitsverzeichnis vor finalem Kopieren.
- „Component Result“: einzelnes Ergebnis je Teilkomponente (`rest_api`, `pybeep`, `firmware_bundle`).

## Plan of Work

### 1) ZIP-Format standardisieren (verbindlicher Vertrag)

Einführung eines festen Paketformats:

- Dateiname (empfohlen): `seva-box-update_<bundle-version>.zip`
- Top-Level Inhalt:
  - `manifest.json` (pflicht)
  - `payload/rest_api/...` (optional)
  - `payload/pybeep_vendor/...` (optional)
  - `payload/firmware/*.bin` (optional, genau 0..1 je Zielboardtyp im ersten Schritt)

Vorgeschlagenes `manifest.json` (Version 1):

    {
      "manifest_version": 1,
      "bundle_version": "2026.02.13-rc1",
      "created_at_utc": "2026-02-13T10:30:00Z",
      "min_installer_api": "0.1.0",
      "components": {
        "rest_api": {
          "present": true,
          "source_dir": "payload/rest_api",
          "target_dir": "/opt/box/rest_api",
          "sha256": "...",
          "version": "0.9.0"
        },
        "pybeep_vendor": {
          "present": true,
          "source_dir": "payload/pybeep_vendor",
          "target_dir": "/opt/box/.vendor/pyBEEP",
          "sha256": "...",
          "version": "1.4.2"
        },
        "firmware_bundle": {
          "present": true,
          "source_file": "payload/firmware/potentiostat.bin",
          "sha256": "...",
          "version": "2.7.0"
        }
      }
    }

Wichtige Regeln:

- Kein `present=true` ohne existierende Quelle.
- SHA256 muss für jede vorhandene Komponente verifiziert werden.
- Unbekannte Komponenten => harter Fehler (`update.manifest_unknown_component`), um stilles Ignorieren zu vermeiden.
- Path Traversal-Schutz (`..`, absolute Pfade, Symlink-Eskapaden) beim Entpacken verpflichtend.

### 2) REST API-Update-Orchestrierung einführen

Neue Endpoint-Familie in `rest_api/app.py`:

- `POST /updates` (multipart: `file=<zip>`) -> erstellt Update-Job und startet Verarbeitung im Hintergrund.
- `GET /updates/{update_id}` -> Polling-Status des Jobs.
- `GET /updates/latest` -> optionaler Convenience-Endpunkt für zuletzt gestarteten Job.

Job-Statusmodell (typed Pydantic) enthält:

- `update_id`, `status` (`queued|running|done|failed|partial`)
- `started_at`, `finished_at`
- `bundle_version`
- `steps`: Liste mit Schritten (`validate_archive`, `apply_rest_api`, `apply_pybeep_vendor`, `stage_firmware`)
- `component_results` mit je:
  - `component`, `action` (`updated|skipped|staged|failed`),
  - `from_version`, `to_version`,
  - `message`, `error_code` (optional)

Fehlerpolitik:

- Adapter-/Systemnahe Fehler in typed API-Error-Codes mappen.
- Keine stillen Fallbacks; bei Manifest-/Checksum-Fehlern sofort klar abbrechen.
- Bei Teilfehlern `partial` erlauben, aber explizit je Komponente berichten.

Ablauf API-seitig:

1. ZIP speichern nach `/opt/box/updates/incoming/{update_id}.zip`.
2. Sicher entpacken nach `/opt/box/updates/staging/{update_id}/`.
3. Manifest laden + validieren.
4. Komponenten sequentiell anwenden:
   - `rest_api`: atomar in Zielverzeichnis austauschen (Backup + replace).
   - `pybeep_vendor`: atomar in `.vendor` austauschen.
   - `firmware_bundle`: nach `/opt/box/firmware/` ablegen, aber nicht flashen.
5. Ergebniszustand schreiben (in-memory + optional persistente Jobdatei), dann Polling-Endpunkt bedienbar halten.

### 3) Firmware-Endpoint erhalten und ergänzen

`POST /firmware/flash` bleibt erhalten.

Ergänzungen:

- Optionales Feld `filename`/`version_hint` oder separater Endpoint `POST /firmware/flash/staged` zur Verwendung der zuletzt gestagten Firmware aus Gesamt-Update.
- Bei Erfolg Rückgabe inkl. verwendeter Firmware-Datei und Version-Hinweis aus Manifest.

### 4) GUI-Integration im Settings-Menü (Ablösung alter Funktion)

MVVM-konform umstellen:

- View (`settings_dialog.py`): Firmware-Group ersetzen durch „Remote Update“-Group:
  - ZIP-Pfad
  - „Browse ZIP…"
  - „Upload & Apply Update"
  - „Firmware jetzt flashen“ (separater Schritt)
  - Statusanzeige letzter Update-Job
- Controller (`settings_controller.py`): neue Handler auf neue UseCases verdrahten.
- Neue UseCases:
  - `UploadRemoteUpdate` (startet `POST /updates`)
  - `PollRemoteUpdateStatus` (fragt `GET /updates/{id}`)
- Neuer Adapter:
  - `update_rest.py` (transportiert `/updates` calls, typed errors)

Legacy entfernen:

- Der bisherige „nur Firmware“-Einstieg in den Settings wird gelöscht.
- Flash-UseCase bleibt als separater Schritt innerhalb des neuen Gesamt-Update-Bereichs verfügbar.

### 5) User-Rückgaben und UX-Feedback definieren

Unmittelbar nach Upload:

- Toast: „Update gestartet (ID: …)“
- UI zeigt `queued/running` + aktuellen Schritt.

Nach Abschluss:

- Erfolg: „Update erfolgreich: API x->y, pyBEEP a->b, Firmware staged v.“
- Partial: „Update teilweise erfolgreich“, plus Box/Komponenten-Details.
- Fehler: eindeutiger Code + Human Message + ggf. Handlungshinweis.

Fehlercodes (Startset):

- `update.invalid_upload`
- `update.manifest_missing`
- `update.manifest_invalid`
- `update.manifest_unknown_component`
- `update.checksum_mismatch`
- `update.apply_rest_api_failed`
- `update.apply_pybeep_failed`
- `update.stage_firmware_failed`

### 6) Version-Checks für User bereitstellen

API-Seite:

- `GET /version` erweitern um:
  - `firmware_staged_version` (aus letztem validen Manifest, falls vorhanden)
  - `firmware_device_version` (wenn durch Geräteabfrage verfügbar; sonst `unknown`)
- Optional separater Endpoint `GET /devices/firmware` mit Slot-basierter Firmware-Version.

GUI-Seite:

- Settings zeigt pro Box:
  - API-Version
  - pyBEEP-Version
  - Geräte-Firmware-Version (pro Box aggregiert oder je Device in Detaildialog)
  - staged Firmware-Version

### 7) Tests und Dokumentation

Tests:

- API Contract Tests für `/updates`:
  - gültiges ZIP -> `done`
  - fehlendes Manifest -> `400`
  - falsche SHA -> `400`
  - nur eine Komponente vorhanden -> `partial` oder `done` mit `skipped`
- GUI/UseCase-Tests:
  - Adapter-Fehler werden in UseCaseError gemappt.
  - Statuspolling aktualisiert ViewModel ohne I/O in View.

Dokumentationsupdates:

- `docs/workflows_rest_api.md`: neuer Workflow „Remote Update“ + Verweis auf Firmware-Flash-Trennung.
- `docs/classes_rest_api.md`: neue Endpoint-/Modulbeschreibung.
- `docs/workflows_seva.md` und `docs/classes_seva.md`: neue Update-UseCases/Adapter/UI-Fluss.

## Concrete Steps

Arbeitsverzeichnis: `/workspace/SEVA_GUI_MVVM`

1) Implementierung vorbereiten

    rg -n "firmware|version|updates|settings" rest_api seva docs

2) API-Änderungen einführen

    # Dateien erweitern: rest_api/app.py (+ ggf. neues rest_api/update_service.py)
    pytest -q

3) GUI-Änderungen einführen

    # Dateien: settings_dialog.py, settings_controller.py, neue adapter/usecases
    pytest -q

4) End-to-End manuell prüfen (Beispiel)

    curl -X POST -H "X-API-Key: ..." -F "file=@seva-box-update_2026.02.13-rc1.zip" http://<box>:8000/updates
    curl -H "X-API-Key: ..." http://<box>:8000/updates/<update_id>
    curl -H "X-API-Key: ..." http://<box>:8000/version

Erwartung (gekürzt):

    {"update_id":"...","status":"queued"}
    {"update_id":"...","status":"done","component_results":[...]}
    {"api":"...","pybeep":"...","firmware_staged_version":"..."}

## Validation and Acceptance

Akzeptanzkriterien:

- Ein valides ZIP startet erfolgreich einen Update-Job und liefert pollbaren Status.
- Manifest- oder Checksum-Fehler sind klar als API-Fehlercode sichtbar.
- Firmware wird im Gesamt-Update nicht automatisch geflasht.
- Der separate Firmware-Flash ist weiterhin aufrufbar und funktionsfähig.
- GUI-Settings zeigen den neuen Gesamt-Update-Flow statt altem „nur Firmware“-Flow.
- User kann API-, pyBEEP- und Firmware-Versionen sichtbar prüfen.

## Idempotence and Recovery

- Upload desselben Bundles ist wiederholbar; `bundle_version` + Hash können zur Duplicate-Erkennung genutzt werden.
- Bei Abbruch im Staging dürfen Zielverzeichnisse unverändert bleiben (atomare Replace-Strategie).
- Vor Überschreiben produktiver Verzeichnisse Backup unter `/opt/box/updates/backups/<timestamp>/` ablegen.
- Recovery: fehlgeschlagenen Job verwerfen, Backup zurückspielen, Endpoint erneut aufrufen.

## Artifacts and Notes

Wichtige Referenzen im Ist-Zustand:

- REST API Firmware-Endpunkt in `rest_api/app.py` (`POST /firmware/flash`).
- Versionsausgabe in `rest_api/app.py` (`GET /version`).
- GUI Firmware-UI in `seva/app/views/settings_dialog.py`.
- GUI Firmware-Aktion in `seva/app/settings_controller.py`.

## Interfaces and Dependencies

Neue/angepasste Interfaces:

- `UpdatePort` in `seva/domain/ports.py` mit Methoden:
  - `start_update(box_id: BoxId, zip_path: str | Path) -> UpdateStartResult`
  - `get_update_status(box_id: BoxId, update_id: str) -> UpdateStatus`
- Adapter `seva/adapters/update_rest.py` implementiert `UpdatePort`.
- UseCases:
  - `seva/usecases/upload_remote_update.py`
  - `seva/usecases/poll_remote_update_status.py`

API-Modelle (in `rest_api/app.py` oder ausgelagert):

- `UpdateStartResponse`
- `UpdateStep`
- `UpdateComponentResult`
- `UpdateStatusResponse`

Abhängigkeiten:

- Standardbibliothek reicht weitgehend (`zipfile`, `hashlib`, `tempfile`, `shutil`, `pathlib`).
- Keine neuen externen Libraries nötig, sofern sichere Entpack-Checks intern implementiert werden.

---

Change note (2026-02-13): Neuer ExecPlan für Remote-Update erstellt, basierend auf aktuellem API-/GUI-Stand und den geforderten Planungsfragen (ZIP-Struktur, Ablauf, Rückgaben, Versionsprüfung, Endpoint-Design).
