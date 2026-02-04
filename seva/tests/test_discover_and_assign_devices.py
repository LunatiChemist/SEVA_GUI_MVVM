from __future__ import annotations

import pytest

from seva.domain.discovery import DiscoveredBox
from seva.domain.ports import UseCaseError
from seva.usecases.discover_and_assign_devices import (
    DiscoverAndAssignDevices,
    DiscoveryRequest,
)
from seva.usecases.discover_devices import MergeDiscoveredIntoRegistry


class _DiscoverStub:
    def __init__(self, discovered):
        self._discovered = list(discovered)

    def __call__(self, *, candidates, api_key=None, timeout_s=0.3):
        return list(self._discovered)


def test_discover_and_assign_assigns_new_urls() -> None:
    discovered = [DiscoveredBox(base_url="http://new", box_id="box1")]
    usecase = DiscoverAndAssignDevices(
        discover=_DiscoverStub(discovered),
        merge=MergeDiscoveredIntoRegistry(),
    )
    result = usecase(
        DiscoveryRequest(
            candidates=["http://seed"],
            api_key=None,
            timeout_s=0.1,
            box_ids=["A", "B"],
            existing_registry={"A": "http://old"},
        )
    )
    assert result.assigned == {"B": "http://new"}
    assert result.normalized_registry == {"A": "http://old", "B": "http://new"}


def test_discover_and_assign_requires_candidates() -> None:
    usecase = DiscoverAndAssignDevices(
        discover=_DiscoverStub([]),
        merge=MergeDiscoveredIntoRegistry(),
    )
    with pytest.raises(UseCaseError) as exc:
        usecase(
            DiscoveryRequest(
                candidates=[],
                api_key=None,
                timeout_s=0.1,
                box_ids=["A"],
                existing_registry={},
            )
        )
    assert exc.value.code == "NO_CANDIDATES"
