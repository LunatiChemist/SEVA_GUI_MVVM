"""ViewModel package for UI state and command surfaces.

Call context:
    ``seva/app/main.py`` and controller/presenter modules import concrete
    viewmodels from this package to bind view callbacks to state transitions.

Dependencies:
    Modules in this package depend on domain types and lightweight formatting
    helpers only. I/O adapters and use-case orchestration remain outside.

Responsibilities:
    - Expose mutable UI state and command intent callbacks.
    - Transform typed domain snapshots into view-facing DTOs.
    - Keep MVVM boundaries explicit by avoiding transport or persistence logic.
"""
