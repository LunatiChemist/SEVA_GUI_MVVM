# Remote-Update-Feature für REST API + GUI Settings umsetzen

Dieses ExecPlan ist ein lebendes Dokument. Die Abschnitte `Progress`, `Surprises & Discoveries`, `Decision Log` und `Outcomes & Retrospective` müssen während der Umsetzung laufend aktualisiert werden.

Dieses Dokument wird gemäß `.agent/PLANS.md` gepflegt. Alle Anforderungen aus `.agent/PLANS.md` gelten vollständig.

## Purpose / Big Picture

Nach dieser Änderung kann ein Benutzer im GUI-Settings-Dialog ein einziges Update-ZIP hochladen, das auf allen ausgewählten Boxen asynchron verarbeitet wird. Die Box installiert daraus `rest_api`, `pyBEEP` und Firmware (inklusive Flash), liefert den Fortschritt über einen Status-Endpunkt, schreibt ein Audit-Log und startet den Service nach erfolgreichem Apply automatisch neu.

Sichtbar ist der Erfolg durch:

- GUI-Flow „Update Package auswählen -> Update starten -> Status pollt bis done“.
- REST-Endpunkte für Start und Status mit stabilen, maschinenlesbaren Ergebnissen.
- Geänderte Versionswerte in `/version` (API/pyBEEP) und Firmware-Versionen pro Gerät nach dem Flash.

## Progress

- [x] (2026-02-13 00:00Z) Anforderungen und Zielbild für Update-Paket, Async-Status, Concurrency-Lock und Audit-Log festgelegt.
- [ ] ZIP-Manifest-Contract und serverseitige Validierung in `rest_api` implementieren.
- [ ] Asynchronen Update-Orchestrator mit per-Box-Tasks und globalem Statusmodell implementieren.
- [ ] Bestehende Firmware-Flash-Logik für Paket-Updates wiederverwenden (kein paralleler Legacy-Pfad).
- [ ] GUI-Settings-Flow von „Firmware-only“ auf „Remote Update Package“ migrieren (inkl. Polling und Ergebnisanzeige).
- [ ] Alte GUI-Pfade entfernen, die durch den neuen Update-Flow ersetzt werden.
- [ ] API-/Adapter-/UseCase-Contract-Tests ergänzen.
- [ ] Dokumentation in `docs/` für neuen Workflow und Endpunkte aktualisieren.
- [ ] End-to-End-Verifikation lokal durchführen und Ergebnisse dokumentieren.

## Surprises & Discoveries

- Beobachtung: Die bestehende REST-API hat bereits einen robusten Firmware-Endpoint (`POST /firmware/flash`) mit Dateivalidierung, typisierten Fehlern und Script-Aufruf.
  Evidence: `rest_api/app.py` enthält vollständigen Flash-Flow inklusive Fehlercodes.

- Beobachtung: Die GUI-Architektur nutzt bereits UseCase -> Port -> Adapter für Firmware, daher lässt sich der neue Update-Flow architekturkonform ergänzen.
  Evidence: `seva/usecases/flash_firmware.py` und `seva/adapters/firmware_rest.py` folgen dem vorhandenen Hexagonal-Schema.

## Decision Log

- Decision: Update-Verarbeitung läuft asynchron über neuen Start-Endpunkt plus Poll-Endpunkt.
  Rationale: ZIP-Upload, Entpacken, Flash und Service-Neustart sind langlaufend; GUI darf nicht blockieren.
  Date/Author: 2026-02-13 / Codex.

- Decision: Firmware wird im Paket-Update aktiv geflasht (nicht nur staged), aber bestehender `/firmware/flash`-Flow bleibt erhalten und wird intern wiederverwendet.
  Rationale: Gewünschtes Verhalten laut Nutzer; gleichzeitig DRY durch Wiederverwendung statt Doppelimplementierung.
  Date/Author: 2026-02-13 / Codex.

- Decision: Nach erfolgreichem Update wird der API-Service automatisch neu gestartet.
  Rationale: Nutzeranforderung; stellt sicher, dass neue API/pyBEEP-Versionen sofort aktiv sind.
  Date/Author: 2026-02-13 / Codex.

- Decision: Kein Signatur-Check, kein Dry-Run, keine Kompatibilitätsmatrix in v1.
  Rationale: KISS/YAGNI für erste produktive Version.
  Date/Author: 2026-02-13 / Codex.

- Decision: Concurrency-Lock und Audit-Log sind Pflicht in v1.
  Rationale: Schutz vor konkurrierenden Updates und nachvollziehbare Betriebsprotokolle.
  Date/Author: 2026-02-13 / Codex.

## Outcomes & Retrospective

Initialer Planungsstand erstellt. Umsetzung noch ausstehend.

Geplantes Zielbild für „done“:

- Neues Remote-Update läuft stabil auf allen ausgewählten Boxen.
- GUI ersetzt den bisherigen Firmware-only-Einstieg durch den Paket-Flow.
- Alle relevanten Versionen sind sichtbar und verifizierbar.

## Context and Orientation

Der aktuelle Stand im Repository:

- `rest_api/app.py` enthält bestehende Endpunkte und den vorhandenen Firmware-Flash-Flow.
- `rest_api/auto_flash_linux.py` implementiert das Linux-Flash-Skript.
- `seva/app/views/settings_dialog.py` enthält derzeit den Firmware-only UI-Bereich.
- `seva/usecases/flash_firmware.py` und `seva/adapters/firmware_rest.py` zeigen die etablierte UseCase/Adapter-Struktur.
- `docs/workflows_rest_api.md` und `docs/workflows_seva.md` dokumentieren vorhandene Flows.

Begriffe in diesem Plan:

- „Async“ bedeutet: Der Start-Endpunkt antwortet schnell mit einer `update_id`; der Fortschritt wird separat abgefragt.
- „Concurrency-Lock“ bedeutet: Nur ein aktiver Update-Job gleichzeitig je Box (optional zusätzlich global pro Service).
- „Audit-Log“ bedeutet: fortlaufende, zeitgestempelte Protokolleinträge zu Start, Teilschritten, Fehlern und Abschluss.

## Plan of Work

### Milestone 1: Update-Paket-Contract und Validierung

In `rest_api` wird ein stabiler Paket-Contract eingeführt, der ein fixes ZIP-Layout mit `manifest.json` und Checksummen definiert. Es werden Pydantic-Modelle für Manifest und Ergebnisobjekte ergänzt, damit oberhalb der Adapter-Grenze keine rohen, unstrukturierten JSON-Daten weitergereicht werden. Validierung umfasst ZIP-Sicherheitschecks (Pfad-Traversal verhindern), Pflichtdateien, Checksummenvergleich und komponentenbezogene Pflichtfelder.

Akzeptanz: Ein gültiges ZIP wird akzeptiert; ein ungültiges ZIP liefert strukturierten Fehlercode und verständliche Meldung.

### Milestone 2: Asynchroner Update-Orchestrator im REST-Backend

Ein neuer Start-Endpunkt nimmt das ZIP entgegen und legt einen Update-Job an. Ein Hintergrund-Worker verarbeitet die Komponenten in klarer Reihenfolge: pyBEEP, rest_api, firmware-flash. Der Worker schreibt laufend Status-Updates in ein in-memory Jobregister plus Audit-Log-Datei unter `/opt/box/updates/audit.log`.

Akzeptanz: `POST /updates/package` gibt `update_id` zurück; `GET /updates/{update_id}` zeigt reproduzierbare Zustände (`queued`, `running`, `done`, `failed`, `partial`).

### Milestone 3: Wiederverwendung Firmware-Flash-Logik

Der Paket-Flow ruft intern denselben Flash-Pfad wie der bestehende `/firmware/flash`-Endpoint auf (gemeinsame Hilfsfunktion in `rest_api/app.py` oder neues Modul), damit Validierung, Script-Aufruf und Fehlerbehandlung identisch bleiben.

Akzeptanz: Firmware aus Paket führt zu demselben technischen Verhalten wie Firmware-only-Upload, inklusive gleicher Fehlersemantik.

### Milestone 4: Service-Neustart und Recovery-Strategie (KISS)

Nach erfolgreichem Apply aller gewählten Komponenten führt der Worker einen automatischen Service-Restart aus (`systemctl restart pybeep-box.service` oder konfigurierbarer Service-Name). Recovery bleibt bewusst einfach: bei Fehler wird Job auf failed gesetzt, Audit enthält Ursache, Nutzer kann korrigiertes oder älteres Paket erneut einspielen.

Akzeptanz: Erfolgreiches Update endet mit dokumentiertem Neustart; bei Fehler bleibt API-Fehlerstatus nachvollziehbar.

### Milestone 5: GUI-Migration im Settings-Dialog

Der Firmware-only-Settings-Bereich wird durch einen Remote-Update-Bereich ersetzt: ZIP auswählen, Update starten, Status anzeigen. Die Architektur bleibt strikt: View nur UI-Events, UseCase orchestriert, Adapter spricht HTTP. Für Polling wird ein neuer UseCase eingeführt, der serverseitigen Status 1:1 darstellt (Server bleibt Source of Truth).

Akzeptanz: Bediener kann aus der GUI ein Paket-Update starten und dessen Status bis Abschluss verfolgen.

### Milestone 6: Versionstransparenz im UI

Versionen werden zentral abrufbar gemacht:

- API + pyBEEP weiterhin über `/version`.
- Firmware-Versionen über neuen Geräte-Endpunkt (z. B. `/devices/firmware`) oder Erweiterung bestehender Device-Daten.

GUI zeigt diese Werte im Settings-Umfeld an, sodass Vorher/Nachher nach Update klar sichtbar ist.

Akzeptanz: Benutzer sieht Versionsstände ohne manuelle Shell-Befehle.

### Milestone 7: Tests und Dokumentation

Contract-getriebene Tests decken UseCase↔Adapter und REST-Contracts ab. UI-Tests bleiben minimal. Dokumentation wird in `docs/workflows_rest_api.md`, `docs/workflows_seva.md` und ggf. `docs/classes_rest_api.md` ergänzt.

Akzeptanz: Testlauf erfolgreich; Doku beschreibt neuen End-to-End-Workflow einschließlich Fehlerfälle.

## Concrete Steps

Arbeitsverzeichnis: Repository-Root `/workspace/SEVA_GUI_MVVM`.

1. Baseline prüfen:

    git status
    pytest -q

2. Neue REST-Modelle und Endpunkte implementieren (Start + Status + optional List).

3. Update-Worker und Audit-Logging ergänzen, Concurrency-Lock einbauen.

4. Firmware-Shared-Helper extrahieren und vom alten plus neuem Flow nutzen.

5. GUI: neue Domain-Types, Port-Methoden, Adapter, UseCases, Settings-Dialog-Callbacks.

6. Alte ersetzte GUI-Pfade entfernen.

7. Tests ergänzen und ausführen:

    pytest -q

8. Manuelle API-Verifikation (lokal laufende API vorausgesetzt):

    curl -X POST http://localhost:8000/updates/package \
      -H "X-API-Key: <key>" \
      -F "file=@sample-update.zip"

    curl -H "X-API-Key: <key>" http://localhost:8000/updates/<update_id>

Erwartung (gekürzt):

    {"update_id":"...","status":"queued"}
    {"update_id":"...","status":"running","components":[...]}
    {"update_id":"...","status":"done","restart":{"ok":true}}

## Validation and Acceptance

Die Änderung gilt als akzeptiert, wenn folgende Verhalten überprüfbar sind:

1. Ein gültiges ZIP startet asynchrones Update und erzeugt `update_id`.
2. Polling liefert nachvollziehbare Statusübergänge und komponentenspezifische Ergebnisse.
3. Firmware im Paket wird tatsächlich geflasht (gleiches Verhalten wie `/firmware/flash`).
4. Concurrency-Lock verhindert parallele konkurrierende Updates.
5. Audit-Log enthält Start, Teilschritte, Fehler oder Erfolg und Neustart-Eintrag.
6. Nach erfolgreichem Ablauf läuft API mit neuen Komponenten weiter (Versionen sichtbar).
7. GUI ersetzt den alten Firmware-only-Einstieg vollständig durch den Paket-Flow.

## Idempotence and Recovery

- ZIP-Validierung und Stage-Schritte sind wiederholbar.
- Bei Fehlern kann derselbe Update-Start erneut mit korrigiertem Paket durchgeführt werden.
- Kein komplexes Rollback in v1: Recovery erfolgt durch erneutes Einspielen eines bekannten guten Pakets.
- Concurrency-Lock wird bei terminalem Status (`done`/`failed`) zuverlässig freigegeben.

## Artifacts and Notes

Geplante wichtige Artefakte während der Umsetzung:

- Beispiel `manifest.json` für Update-ZIP.
- Beispiel-Audit-Log-Auszug mit Erfolg und Fehlerfall.
- Kurzer Curl-Transkript für Start + Poll.
- Testprotokollauszug (relevante neue Tests).

## Interfaces and Dependencies

REST (neu/erweitert):

- `POST /updates/package` (multipart ZIP, asynchroner Jobstart)
- `GET /updates/{update_id}` (Jobstatus)
- optional `GET /updates` (letzte Jobs)
- bestehend: `POST /firmware/flash` bleibt verfügbar

Domain/Adapter (GUI):

- Neuer Port für Package-Update-Operationen (start/poll).
- UseCases für `StartRemoteUpdate` und `PollRemoteUpdateStatus`.
- Typed DTOs für Update-Status statt unstrukturierter Dict-Ketten oberhalb Adaptergrenze.

Empfohlene v1-Grenzwerte:

- ZIP max 500 MB
- Upload-Timeout 120s
- Poll-Timeout 10s
- Poll-Intervall 1-2s
- Per-Box Apply-Timeout 10 min
- Gesamt-Timeout 30 min

---

Änderungshistorie dieses ExecPlans:

- 2026-02-13: Initiale Fassung aus den abgestimmten Chat-Entscheidungen erstellt.
