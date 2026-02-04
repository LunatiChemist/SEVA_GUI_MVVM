# Document seva/adapters in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

Adapters implement ports and are the boundary between the GUI domain and external systems (REST API, filesystem, discovery, mocks). This plan produces detailed documentation for every adapter so a new developer can trace how domain objects become HTTP requests or filesystem writes, and how errors are surfaced back to usecases.

Success is observable when:

- Every file in `seva/adapters` starts with a Google-style module docstring describing purpose, dependencies, and call contexts.
- Every class/function has a Google-style docstring with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments explain complex mapping, error translation, and HTTP payload construction.
- `docs/classes_seva.md` and `docs/workflows_seva.md` include adapter responsibilities and their mapped ports.

## Progress

- [x] (2026-02-04 00:35Z) Map adapter implementations to domain ports and GUI usecases.
- [ ] (2026-02-11 00:00Z) Add/expand module docstrings for each adapter file.
- [ ] (2026-02-11 00:00Z) Add/expand class and function docstrings, including call-chain and error cases.
- [ ] (2026-02-11 00:00Z) Add inline comments for complex HTTP/IO logic and error translation.
- [x] (2026-02-04 00:35Z) Update `docs/classes_seva.md` and `docs/workflows_seva.md` with adapter mapping.
- [ ] (2026-02-11 00:00Z) Final consistency pass for Google style and completeness.

## Surprises & Discoveries

- Observation: Discovery adapter maps to `DeviceDiscoveryPort` in `seva/domain/discovery.py`, not to `seva/domain/ports.py`.
  Evidence: `seva/usecases/discover_devices.py` depends on `DeviceDiscoveryPort`, and `seva/adapters/discovery_http.py` implements that protocol.
- Observation: Existing architecture docs already covered adapter names, but did not explicitly tie each adapter to call chains and endpoint/file-path responsibilities.
  Evidence: Added explicit adapter-to-usecase mapping and endpoint/file persistence notes in `docs/classes_seva.md` and `docs/workflows_seva.md`.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/adapters`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent
- Decision: Treat mapping + docs update as the first completed milestone before editing adapter source files.
  Rationale: Clarifies call-chain context first, so function-level docstrings can reference real workflows consistently.
  Date/Author: 2026-02-04 / Agent

## Outcomes & Retrospective

- Milestone update (2026-02-04): Adapter/port/usecase mapping is now explicit in both architecture docs. Remaining work is concentrated in adapter source files (module/class/function docstrings and inline comments), followed by validation and consistency pass.

## Context and Orientation

Adapters implement port interfaces defined in `seva/domain/ports.py`. They should not contain orchestration; they only translate domain types into external calls and return domain types or typed errors. Adapters include REST clients, firmware/discovery helpers, storage/local files, and mock implementations used in tests or offline scenarios.

Key files (non-exhaustive):

- `seva/adapters/http_client.py`
- `seva/adapters/device_rest.py`
- `seva/adapters/job_rest.py`
- `seva/adapters/firmware_rest.py`
- `seva/adapters/storage_local.py`
- `seva/adapters/discovery_http.py`
- `seva/adapters/api_errors.py`
- `seva/adapters/job_rest_mock.py`
- `seva/adapters/relay_mock.py`

## Plan of Work

1) Map each adapter to its port and call-chains.
   - Identify which port interface each adapter implements.
   - Note which usecases invoke each adapter and which REST endpoints or filesystem locations are used.
   - Record these mappings in `docs/classes_seva.md` and `docs/workflows_seva.md`.

2) Add module docstrings.
   - Each adapter file begins with a Google-style module docstring that explains purpose, dependencies, and typical call contexts.

3) Add/expand class/function docstrings.
   - Include summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
   - Explicitly document how domain types are converted to request payloads and how responses are normalized.

4) Add inline comments for complex logic.
   - Focus on serialization/deserialization, error mapping, and authentication headers.

5) Update documentation files.
   - Ensure adapter responsibilities and relationships to ports are described in `docs/classes_seva.md`.
   - Ensure workflows show adapter roles in `docs/workflows_seva.md`.

6) Final pass for consistency.

## Concrete Steps

All steps are run from the repository root (`c:\Users\LunaP\OneDrive - UBC\Dokumente\Chemistry\Potentiostats\GUI Testing\SEVA_GUI_MVVM`).

1) Inspect adapter files:

    sed -n '1,200p' seva/adapters/http_client.py
    sed -n '1,200p' seva/adapters/device_rest.py
    sed -n '1,200p' seva/adapters/job_rest.py
    sed -n '1,200p' seva/adapters/firmware_rest.py
    sed -n '1,200p' seva/adapters/storage_local.py
    sed -n '1,200p' seva/adapters/discovery_http.py
    sed -n '1,200p' seva/adapters/api_errors.py
    sed -n '1,200p' seva/adapters/job_rest_mock.py
    sed -n '1,200p' seva/adapters/relay_mock.py

2) Add/expand docstrings and inline comments in each file.

3) Update `docs/classes_seva.md` and `docs/workflows_seva.md`.

4) Optional validation (documentation only):

    pytest -q

## Validation and Acceptance

- All adapter files have Google-style module docstrings with call contexts and dependencies.
- All classes/functions have Google-style docstrings with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex IO/HTTP/error handling logic.
- `docs/classes_seva.md` and `docs/workflows_seva.md` describe adapter mappings and roles.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert and reapply documentation-only changes with `git restore <file>` as needed.

## Artifacts and Notes

Expected artifacts:

- Updated docstrings and inline comments in `seva/adapters/*.py`.
- Updated `docs/classes_seva.md` and `docs/workflows_seva.md` sections for adapters.

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- Port interfaces in `seva/domain/ports.py`
- REST API endpoints in `rest_api/app.py`

---

Change note: Initial plan created to cover the adapter subsystem in deep detail.
