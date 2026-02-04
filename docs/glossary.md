# Glossary

This glossary mixes domain terms (runs, wells, boxes) with MVVM + Hexagonal
architecture terms so new developers can reason about the system without prior
framework knowledge. Each entry includes a short definition and a pointer to
where the concept lives in code.

## MVVM + Hexagonal terms

**View**  
UI widgets and rendering logic only. Views expose callbacks and never perform
I/O or business logic. See `seva/app/views/*`.

**ViewModel**  
State + commands used by views. ViewModels coordinate UI state but do not touch
adapters or build API payloads. See `seva/viewmodels/*`.

**UseCase**  
Workflow orchestration that coordinates domain rules and adapters (e.g., save
layout, start jobs, cancel runs). See `seva/usecases/*`.

**Adapter**  
I/O boundary implementation for a port (HTTP, filesystem, relay, discovery).
Adapters are called by use cases or controllers but never orchestrate flows.
See `seva/adapters/*`.

**Port**  
A protocol that defines the boundary between use cases and external systems.
Adapters implement ports, and use cases depend on ports. See
`seva/domain/ports.py`.

**Domain type**  
Value objects that normalize and validate identifiers and snapshots early.
See `seva/domain/entities.py` for `RunId`, `GroupId`, `WellId`, and more.

## Domain terms

**Box**  
A hardware enclosure (Pi + potentiostat) addressed by a `BoxId`. See
`seva/domain/entities.py`.

**Run**  
An individual experiment execution on the backend, identified by a `RunId`. See
`seva/domain/entities.py`.

**Group**  
A collection of related runs started together, identified by a `GroupId` (or
`RunGroupId` in ports). See `seva/domain/entities.py` and `seva/domain/ports.py`.

**Well**  
A plate position within a batch plan. Represented by `WellId`. See
`seva/domain/entities.py`.

**Mode**  
The electrochemistry mode applied to a well (e.g., CV, EIS). Mode tokens are
normalized via domain utilities (see `seva/domain/modes.py`).

**Layout**  
Saved plate configuration (selection + parameters) persisted locally by the
storage adapter. See `seva/adapters/storage_local.py` and
`seva/usecases/save_plate_layout.py`.

## Code examples (MVVM + Hexagonal call chain)

### View → ViewModel callbacks

Views receive callbacks that delegate to ViewModel commands (no I/O in views).

```python
self.wellgrid = WellGridView(
    self.win.wellgrid_host,
    boxes=initial_boxes,
    on_select_wells=lambda sel: self.plate_vm.set_selection(sel),
    on_copy_params_from=lambda wid: self.plate_vm.cmd_copy_from(wid),
    on_paste_params_to_selection=self.plate_vm.cmd_paste_to_selection,
)
```

Source: `seva/app/main.py`

### UseCase → Port (adapter boundary)

Use cases call ports to persist or fetch data. Ports are implemented by
adapters.

```python
return self.storage.save_layout(name, payload)
```

Source: `seva/usecases/save_plate_layout.py`

### Adapter implements a Port

Adapters implement port methods to perform I/O. This adapter writes JSON layouts
to disk.

```python
def save_layout(self, name: str, payload: Dict) -> Path:
    path = self._layout_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return path
```

Source: `seva/adapters/storage_local.py`
