# Replace GUI network scan discovery with mDNS and add FastAPI service advertisement

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` are maintained in line with `.agent/PLANS.md`.

## Purpose / Big Picture

After this change, end users can discover Raspberry Pi devices automatically on the local LAN without entering IPs or scanning subnets. The backend publishes an IPv4 mDNS service (`_myapp._tcp.local.`), and the desktop GUI discovers that service, validates `/health`, and auto-fills configured box URLs.

## Progress

- [x] (2026-02-18 00:00Z) Reviewed current discovery flow (CIDR/base URL probing) and startup lifecycle in `rest_api/app.py`.
- [x] (2026-02-18 00:10Z) Replaced discovery domain/use case contracts to mDNS-first timing-based discovery inputs.
- [x] (2026-02-18 00:20Z) Replaced adapter implementation with Zeroconf browse + IPv4 extraction + `/health` validation.
- [x] (2026-02-18 00:30Z) Added async GUI discovery orchestration in `DiscoveryController` and updated settings/discovery result view labels/columns.
- [x] (2026-02-18 00:40Z) Added backend `rest_api/mdns_service.py` and integrated registration/deregistration into FastAPI lifespan.
- [x] (2026-02-18 00:45Z) Updated docs and dependencies for Zeroconf-based discovery.
- [ ] (2026-02-18 00:46Z) Commit changes and create PR.

## Surprises & Discoveries

- Observation: The original discovery controller executed synchronously and blocked the UI during probing.
  Evidence: `seva/app/discovery_controller.py` called the use case directly from the button handler path.

- Observation: Existing discovery relied on candidate URLs and derived CIDR hints from configured addresses.
  Evidence: `_build_discovery_candidates` logic in the previous controller implementation.

## Decision Log

- Decision: Keep existing adapter filename (`seva/adapters/discovery_http.py`) while replacing implementation with mDNS to minimize wiring churn.
  Rationale: Reduces integration risk and follows minimal-invasive change requirement.
  Date/Author: 2026-02-18 / Codex

- Decision: Discovery waits fixed 2.5 seconds and never exits early.
  Rationale: Matches explicit UX requirement for fixed 2–3 second browse window.
  Date/Author: 2026-02-18 / Codex

- Decision: GUI filters by `/health` HTTP 200 only and ignores timeouts/errors silently.
  Rationale: Matches requirement and avoids noisy UX.
  Date/Author: 2026-02-18 / Codex

## Outcomes & Retrospective

The codebase now uses mDNS for both service advertisement (backend) and discovery (GUI) with IPv4-only behavior. Legacy scan/candidate construction paths were removed from active flow. Remaining completion step is commit + PR metadata.

## Context and Orientation

Discovery touches these modules:

- `rest_api/app.py` lifespan startup/shutdown.
- `rest_api/mdns_service.py` for backend service registration.
- `seva/domain/discovery.py` for discovery DTO/port contracts.
- `seva/adapters/discovery_http.py` for Zeroconf browse and health validation.
- `seva/usecases/discover_devices.py` and `seva/usecases/discover_and_assign_devices.py` for orchestration.
- `seva/app/discovery_controller.py` for non-blocking GUI execution.
- `seva/app/views/settings_dialog.py` and `seva/app/views/discovery_results_dialog.py` for UI behavior.

## Plan of Work

Refactor from candidate-driven network scanning to fixed-window mDNS browsing by updating contracts first, then adapter and use case orchestration, then GUI controller threading/UI display, then backend startup advertisement and docs/deps.

## Concrete Steps

From repo root:

    python -m compileall rest_api seva

Expected outcome:

    Compiles updated modules without syntax errors.

## Validation and Acceptance

Acceptance is:

- Backend starts and registers `_myapp._tcp.local.` on IPv4 at port 8000, then deregisters on shutdown.
- GUI “Geräte suchen” action does not block UI thread and performs fixed-duration discovery.
- GUI only accepts devices with `GET /health` HTTP 200.
- Discovery result payload includes `name`, `ip`, `port`, `health_url`, `properties`.

## Idempotence and Recovery

All edits are idempotent text/code changes. If runtime discovery fails in a specific environment, fallback behavior is a user-visible “no devices found” state without crashes.

## Artifacts and Notes

Implementation uses `zeroconf` dependency added to both `requirements.txt` and `pyproject.toml` for reproducible installs.

## Interfaces and Dependencies

- Added dependency: `zeroconf>=0.132`.
- `DeviceDiscoveryPort.discover(duration_s, health_timeout_s)` returns `DiscoveredBox` records.
- `MdnsRegistrar.register()` and `.deregister()` encapsulate backend lifecycle publication.
