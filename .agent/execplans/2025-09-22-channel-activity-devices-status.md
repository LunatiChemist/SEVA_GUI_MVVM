# Implement background channel activity polling via /devices/status

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `/workspace/SEVA_GUI_MVVM/.agent/PLANS.md` and must be maintained in accordance with that file.

## Purpose / Big Picture

Users need to see live channel activity at all times, even when no run group is selected. The GUI will poll a new REST endpoint (`/devices/status`) that returns per-slot status and will render it in the Channel Activity tab. Polling should occur every 2 seconds and back off to 10 seconds if there is no change. The new endpoint should use the existing `SlotStatus` shape so the GUI can consume it with minimal mapping, treating `done` like `idle`.

## Progress

- [x] (2025-09-22) Create `/devices/status` endpoint in `rest_api/app.py` returning `SlotStatus` with `idle` support.
- [x] (2025-09-22) Extend domain port and REST adapter to fetch `/devices/status`.
- [x] (2025-09-22) Add a small use case to poll device status and map slots to wells.
- [x] (2025-09-22) Add background polling loop in `RunFlowPresenter` with 2s→10s backoff and update Channel Activity via `ProgressVM`.
- [ ] (2025-09-22) Validate behavior via manual API checks and note expected output in the plan.

## Surprises & Discoveries

- Observation: `SlotStatus` lives only in `rest_api/app.py`, so the GUI needs its own explicit DTO for device activity.
  Evidence: `SlotStatus` is defined in `rest_api/app.py` and not exported in the client domain modules.

## Decision Log

- Decision: Use `/devices/status` returning a list of `SlotStatus` (including new `idle` status) to keep payload minimal and compatible.
  Rationale: Reuses existing data structure and avoids extra mapping/validation in the GUI.
  Date/Author: 2025-09-22 / assistant.
- Decision: Introduce `seva/domain/device_activity.py` with `DeviceActivitySnapshot` and `SlotActivityEntry` as explicit DTOs.
  Rationale: Keeps ViewModels independent from UseCases while avoiding raw dicts above the adapter boundary.
  Date/Author: 2025-09-22 / assistant.

## Outcomes & Retrospective

- Not completed yet.

## Context and Orientation

The REST server lives in `rest_api/app.py` and already exposes `/devices` and `/jobs/status`. It maintains shared state in `DEV_META`, `SLOT_RUNS`, and `JOBS`. `SlotStatus` is a Pydantic model used in job status payloads. The GUI is in `seva/app`, with background polling managed by `RunFlowPresenter` using `PollingScheduler`. Channel Activity updates flow through `ProgressVM` into `ChannelActivityView`.

“Slot” refers to server-side device labels (e.g., `slot01`). “Well” refers to GUI labels (e.g., `A1`). The mapping is built in `seva/domain/mapping.py` using slot labels from `/devices`.

## Plan of Work

First, add a `/devices/status` endpoint in `rest_api/app.py`. It should iterate over registered slots, look up their current run in `SLOT_RUNS`, and return the `SlotStatus` entry from the corresponding job when a run exists. When a slot is free, return a `SlotStatus` with status `idle` and empty timestamps/messages. Extend `SlotStatus` to allow the new `idle` state.

Second, update `seva/domain/ports.py` to add a `list_device_status(box_id)` (name TBD but consistent) method on `DevicePort`, and implement it in `seva/adapters/device_rest.py` to call `/devices/status` and return the list.

Third, add a small use case (new module under `seva/usecases/`) that calls the device port for each box, builds a slot-to-well mapping using `extract_slot_labels` + `build_slot_registry`, and returns a list of well/status pairs suitable for the Channel Activity UI. Keep the DTO explicit (dataclass) so that above-adapter layers do not pass raw dicts.

Fourth, add a background polling loop in `seva/app/run_flow_presenter.py` using the existing `PollingScheduler`. The loop should:
- run every 2 seconds initially,
- compare the new activity signature to the previous one,
- back off in 2-second increments up to 10 seconds when there is no change,
- reset to 2 seconds on change,
- call `ProgressVM` to update activity and timestamp.

Finally, ensure Channel Activity treats `done` as `idle` (either in the new mapping or in `ProgressVM`).

## Concrete Steps

All commands are run from `/workspace/SEVA_GUI_MVVM`.

1) Edit `rest_api/app.py` to add `/devices/status`.
2) Edit `seva/domain/ports.py` and `seva/adapters/device_rest.py` for the new call.
3) Add new use case module under `seva/usecases/`.
4) Update `seva/app/controller.py` to construct the new use case and `seva/app/run_flow_presenter.py` to schedule polling.
5) Update `seva/viewmodels/progress_vm.py` (or new helper) to apply activity updates.

## Validation and Acceptance

Manual validation (example):

- Start REST server and call:
    curl http://<box>/devices/status

- Expect a JSON list of objects shaped like `SlotStatus`, including entries with `status: "idle"` when not in use.

- In the GUI, Channel Activity should update every 2 seconds and still update when no run group is selected. If activity is unchanged, polling interval should back off up to 10 seconds.

## Idempotence and Recovery

All changes are additive. If any step fails, revert the file edits and re-apply in smaller increments. The new endpoint is safe to call repeatedly.

Plan updates: updated progress, discoveries, and decisions after implementation (2025-09-22).
