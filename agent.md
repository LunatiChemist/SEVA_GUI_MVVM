# SEVA MVVM Pro — Refactor Guide (Phase A → D)

> **Scope:** This replaces the previous Phase-2 agent guide.  
> Defines non-negotiable architectural rules, contracts, and quality gates so Codex delivers cohesive increments.  
> **Current focus:** **Phase A – Domain Kernel (Value Objects, Entities, Snapshot Normalizer).**  
> Later phases (B–E) are contextual; **Phase B (RunFlowCoordinator)** and **Phase E (Discovery)** require design reviews before implementation.

---

## Roles

| Role | Responsibility |
|------|----------------|
| **Pro (Product/Architect)** | Sets priorities, approves designs & merges. |
| **Codex (Implementer)** | Delivers small, testable PRs strictly following this guide. |
| **Maintainer** | Branching, CI, release hygiene. |

---

## Architecture Principles (Invariants)

### MVVM + Hexagon (unchanged)
- **Views (Tkinter)** = UI-only — no HTTP, no domain logic, no mapping.  
- **ViewModels** = State + Commands, no I/O.  
- **UseCases** = Orchestration (start / validate / poll / cancel / download / layouts / test).  
- **Adapters** = pure port implementations (REST / Storage); no orchestration inside adapters.

### Phase-Level Commitments
- **One job per well** (no signature grouping).  
- **Server-driven progress** is the single source of truth (status / progress_pct / remaining_s / timestamps). No client math.  
- **No fallbacks / legacy branches.** When a path is replaced, the old one is deleted.  
- **Settings & Layouts = JSON only** (flat keys; no nested legacy).  
- **Plan** carries `experiment`, optional `subdir`, `client_datetime`; server builds run paths.

### Refactor Guardrails (new)
- **Domain types only** across UseCases.  
  - Input = `ExperimentPlan`, Output = `GroupSnapshot`.  
  - No raw dicts in UseCases.  
- **Single validation path:** Client does pre-checks (selection / required fields), server validates modes.  
- **Unified error policy:** Adapters raise typed errors; UseCases map logical errors; Views toast – no double wrapping.

---

## Phase Plan (A → E)

### Phase A — Domain Kernel (**this phase**)
**Goal:** Replace loose dicts with strong domain types and normalize poll snapshots.

**Deliverables**
- `seva/domain/entities.py`  
  - **Value Objects:** `GroupId`, `RunId`, `WellId`, `BoxId`, `ModeName`, `ClientDateTime`, `ServerDateTime`, `ProgressPct`, `Seconds`.  
  - **Entities / Aggregates:**  
    - `PlanMeta` (`experiment`, `subdir?`, `client_dt`, `group_id`)  
    - `ModeParams` (base) + `CVParams` (first impl; others stubs)  
    - `WellPlan` (`well: WellId`, `mode: ModeName`, `params: ModeParams`)  
    - `ExperimentPlan` (`meta: PlanMeta`, `wells: list[WellPlan]`)  
    - `RunStatus` (`run_id`, `phase`, `progress?`, `remaining_s?`, `error?`)  
    - `BoxSnapshot` (`box`, `progress?`, `remaining_s?`)  
    - `GroupSnapshot` (`group`, `runs`, `boxes`, `all_done`)  
- `seva/domain/naming.py` — `make_group_id(meta) → GroupId`, sanitizers.  
- `seva/domain/params/cv.py` — `CVParams.from_form(...) → CVParams`, `.to_payload()`.  
- Stub modules for AC/DC/EIS/CDL (with comments only).  
- `seva/domain/snapshot_normalizer.py` — `normalize_status(raw) → GroupSnapshot`.  
- **UseCase change:** `PollGroupStatus` returns `GroupSnapshot` via normalizer.  
- **Remove:** Any client progress math and legacy branches in polling.

**Acceptance**
- `pytest -q` green for new domain units (naming, normalizer).  
- GUI starts and polls as before; Run Overview uses `GroupSnapshot` internally.  
- No raw dicts leak from `PollGroupStatus` to VMs.

---

### Phase B — RunFlowCoordinator (design review before coding)
**Intent:** Pull orchestration out of `main.py`; linearize flow; fix poll reschedule; add on-complete hook.

**Public surface (draft)**  
- `prepare_plan(vm_state) → ExperimentPlan`  
- `validate_or_start(plan) → Validations | GroupId`  
- `poll_once(group) → GroupSnapshot` (reschedule only if active and not `all_done`)  
- `on_completed(group)` → triggers `DownloadGroupResults`.  

**Remove:** `finally: reschedule` patterns in polling; legacy `all_or_nothing` switches.

---

### Phase C — Adapters & Error Policy
- Add mapping helpers (`to_start_payload`, `from_status_payload`).  
- Typed exceptions only; drop broad `except Exception`.  
- UseCases don’t re-wrap transport errors.

---

### Phase D — VM & View Trimming
- `ExperimentVM` → form state holder (uses PlanBuilder/Domain).  
- `ProgressVM` → consumes `GroupSnapshot` (no dict gymnastics).  
- Views = UI-only.

---

### Phase E — Orchestrator / Discovery (Design Review before coding)
- Interfaces only: `RunQueue`, `Scheduler` (strategy stub).  
- Discovery design per PDF approach; implement later.

---

## Ticket Template (mandatory)

**Title:** `[Phase X] <Focused change>`  
**Context & Intent:** 3–5 sentences explaining why (this refers to MVVM/Hex invariants).  
**Target State:** New/changed classes + public methods (signatures only).  
**Files to Touch:** Exact paths only.  
**Tasks:** Small, linear steps.  
**Out of Scope:** Everything not explicitly targeted.  
**Acceptance:** Observable outcomes + manual checklist.  
**Tests:** At least one unit test per domain addition.

---

## Quality Gates

- No raw dicts in UseCases.  
- No UI logic outside Views/VMs.  
- No client progress math.  
- No legacy/fallbacks after merge.  
- Docstrings for each class/method (1–2 lines + key steps).  
- `pytest -q` must pass (CI green).