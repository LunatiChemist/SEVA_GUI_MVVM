from __future__ import annotations

from typing import Dict

from seva.viewmodels.experiment_vm import ExperimentVM


def make_experiment_vm_with_fields(fields: Dict[str, str]) -> ExperimentVM:
    vm = ExperimentVM()
    vm.fields = dict(fields)
    return vm


__all__ = ["make_experiment_vm_with_fields"]
