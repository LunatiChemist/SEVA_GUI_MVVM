"""Use case for discovery and assignment of devices to slots."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from seva.domain.discovery import DiscoveredBox
from seva.domain.ports import UseCaseError
from seva.usecases.discover_devices import DiscoverDevices, MergeDiscoveredIntoRegistry
from seva.usecases.error_mapping import map_api_error


@dataclass(frozen=True)
class DiscoveryRequest:
    """Input payload for discovery-and-assignment orchestration.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    duration_s: float
    health_timeout_s: float
    box_ids: Sequence[str]
    existing_registry: Mapping[str, str]


@dataclass(frozen=True)
class DiscoveryResult:
    """Output payload for discovery-and-assignment orchestration.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    discovered: Tuple[DiscoveredBox, ...]
    normalized_registry: Dict[str, str]
    assigned: Dict[str, str]
    skipped_urls: Tuple[str, ...]
    message: str


@dataclass
class DiscoverAndAssignDevices:
    """Orchestrate discovery and assignment to available slots."""

    discover: DiscoverDevices
    merge: MergeDiscoveredIntoRegistry

    def __call__(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Discover devices, merge URLs, and assign new URLs to empty slots.

        Args:
            request: Discovery timing plus current registry and slot ids.

        Returns:
            DiscoveryResult: Discovered boxes, normalized registry, assignments,
            skipped URLs, and a summary message for the UI.

        Side Effects:
            Performs network discovery through ``DiscoverDevices``.

        Call Chain:
            Settings scan action -> ``DiscoveryController`` ->
            ``DiscoverAndAssignDevices.__call__``.

        Usage:
            Auto-populates empty box slots while preserving existing mappings.

        Raises:
            UseCaseError: If adapter discovery fails and error mapping applies.
        """
        try:
            discovered = self.discover(
                duration_s=request.duration_s,
                health_timeout_s=request.health_timeout_s,
            )
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="DISCOVERY_FAILED",
                default_message="Discovery failed.",
            ) from exc

        discovered_list = list(discovered or [])
        normalized_registry = self._normalize_registry(
            request.box_ids,
            request.existing_registry,
        )

        if not discovered_list:
            message = "Discovery finished. No devices found."
            return DiscoveryResult(
                discovered=tuple(),
                normalized_registry=normalized_registry,
                assigned={},
                skipped_urls=tuple(),
                message=message,
            )

        merged_registry = self.merge(
            discovered=discovered_list,
            registry=dict(request.existing_registry),
        )

        assigned, skipped, normalized = self._assign_new_urls(
            box_ids=request.box_ids,
            existing_registry=normalized_registry,
            merged_registry=merged_registry,
        )

        message = self._build_message(discovered_list, assigned, skipped)

        return DiscoveryResult(
            discovered=tuple(discovered_list),
            normalized_registry=normalized,
            assigned=assigned,
            skipped_urls=tuple(skipped),
            message=message,
        )

    @staticmethod
    def _normalize_registry(
        box_ids: Sequence[str],
        registry: Mapping[str, str],
    ) -> Dict[str, str]:
        """Return a normalized box-id keyed registry for configured slots.

        Args:
            box_ids: Configured box identifiers from settings.
            registry: Existing persisted mapping.

        Returns:
            Dict[str, str]: Mapping with all ``box_ids`` present.
        """
        return {
            str(box_id): str(registry.get(box_id, "") or "") for box_id in box_ids
        }

    @staticmethod
    def _assign_new_urls(
        *,
        box_ids: Sequence[str],
        existing_registry: Mapping[str, str],
        merged_registry: Mapping[str, str],
    ) -> Tuple[Dict[str, str], list[str], Dict[str, str]]:
        """Assign newly discovered URLs into currently empty box slots.

        Args:
            box_ids: Ordered configured slot identifiers.
            existing_registry: Current slot-to-url mapping.
            merged_registry: Alias-to-url registry after discovery merge.

        Returns:
            Tuple[Dict[str, str], list[str], Dict[str, str]]: Assigned slots,
            skipped URLs, and the final normalized slot registry.
        """
        normalized_map = {
            str(box_id): str(existing_registry.get(box_id, "") or "") for box_id in box_ids
        }
        existing_urls = {url for url in normalized_map.values() if url}
        available_slots = [box_id for box_id, url in normalized_map.items() if not url]

        new_urls: list[str] = []
        seen_urls: set[str] = set()
        for url in merged_registry.values():
            trimmed = str(url or "").strip()
            if trimmed and trimmed not in seen_urls:
                seen_urls.add(trimmed)
                new_urls.append(trimmed)

        assigned: Dict[str, str] = {}
        skipped: list[str] = []
        for url in new_urls:
            if url in existing_urls:
                continue
            if not available_slots:
                skipped.append(url)
                continue
            # Fill slots in settings order to keep assignment deterministic.
            box_id = available_slots.pop(0)
            normalized_map[box_id] = url
            assigned[box_id] = url
            existing_urls.add(url)

        return assigned, skipped, normalized_map

    @staticmethod
    def _build_message(
        discovered: Iterable[DiscoveredBox],
        assigned: Mapping[str, str],
        skipped: Sequence[str],
    ) -> str:
        """Build a user-facing summary of discovery and assignment outcomes.

        Args:
            discovered: Unique discovery hits from the network probe.
            assigned: Newly assigned ``box_id -> url`` mappings.
            skipped: URLs that could not be assigned due to no free slots.

        Returns:
            str: Message suitable for settings status banners/logs.
        """
        summary_seen: set[tuple[str, str, str]] = set()
        summary_parts: list[str] = []
        for box in discovered:
            base_url = f"http://{box.ip}:{box.port}".strip()
            if not base_url:
                continue
            key = (base_url, box.name, box.health_url)
            if key in summary_seen:
                continue
            summary_seen.add(key)
            summary_parts.append(f"{base_url} ({box.name})")

        found_summary = ", ".join(summary_parts) if summary_parts else "none"
        message_bits = [f"Found: {found_summary}"]

        if assigned:
            assigned_summary = ", ".join(
                f"{box_id}={url}" for box_id, url in assigned.items()
            )
            message_bits.append(f"Assigned {assigned_summary}")

        if skipped:
            skipped_summary = ", ".join(skipped)
            message_bits.append(f"No free slots for {skipped_summary}")

        return "Discovery finished. " + "; ".join(message_bits)


__all__ = ["DiscoverAndAssignDevices", "DiscoveryRequest", "DiscoveryResult"]
