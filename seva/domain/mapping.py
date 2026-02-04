"""Mapping helpers between hardware slots and logical well identifiers.

Use cases call these functions when translating `/devices` responses into
deterministic well assignments used by planning and polling flows.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


SlotRegistry = Dict[Tuple[str, int], str]
WellRegistry = Dict[str, Tuple[str, int]]


def extract_device_entries(devices_payload: Any) -> List[Mapping[str, Any]]:
    """Normalize a /devices response into a list of device entries."""
    if isinstance(devices_payload, dict):
        entries = devices_payload.get("devices")
    else:
        entries = devices_payload
    if not isinstance(entries, list):
        raise RuntimeError("devices payload: expected list of device entries")
    return [entry for entry in entries if isinstance(entry, dict)]


def extract_slot_labels(devices_payload: Any) -> List[str]:
    """Return slot labels from a /devices payload or device entries."""
    slots: List[str] = []
    if isinstance(devices_payload, dict):
        raw_slots = devices_payload.get("slots")
        if isinstance(raw_slots, list):
            slots = [str(item) for item in raw_slots if str(item).strip()]
    if not slots:
        entries = extract_device_entries(devices_payload)
        slots = [
            str(entry.get("slot"))
            for entry in entries
            if isinstance(entry.get("slot"), str) and entry.get("slot").strip()
        ]
    seen = set()
    deduped: List[str] = []
    for slot in slots:
        if slot in seen:
            continue
        seen.add(slot)
        deduped.append(slot)
    return deduped


def parse_slot_number(slot_label: str) -> int:
    """Parse slot label strings like ``slot01`` into integers."""
    if not isinstance(slot_label, str) or not slot_label.strip():
        raise ValueError("Slot label must be a non-empty string.")
    match = re.match(r"^slot(\d+)$", slot_label.strip().lower())
    if not match:
        raise ValueError(f"Unsupported slot label '{slot_label}'.")
    return int(match.group(1))


def build_slot_registry(
    box_order: Iterable[str],
    slots_by_box: Mapping[str, Iterable[str]],
) -> Tuple[WellRegistry, SlotRegistry]:
    """Build bidirectional well/slot mappings based on server slot labels."""
    well_to_slot: WellRegistry = {}
    slot_to_well: SlotRegistry = {}
    offset = 0

    for box in box_order:
        slots = list(slots_by_box.get(box) or [])
        if not slots:
            raise ValueError(f"No slots provided for box '{box}'.")
        slot_numbers = sorted(parse_slot_number(slot) for slot in slots)
        max_slot = max(slot_numbers)
        for slot_num in slot_numbers:
            well_number = offset + slot_num
            well_id = f"{box}{well_number}"
            key = (box, slot_num)
            if well_id in well_to_slot or key in slot_to_well:
                raise ValueError(
                    f"Duplicate well mapping for box '{box}' slot {slot_num:02d}."
                )
            well_to_slot[well_id] = key
            slot_to_well[key] = well_id
        offset += max_slot

    return well_to_slot, slot_to_well


def normalize_slot_registry(raw_registry: Any) -> SlotRegistry:
    """Validate and normalize a slot registry from an adapter."""
    if not isinstance(raw_registry, Mapping):
        return {}
    normalized: SlotRegistry = {}
    for key, value in raw_registry.items():
        if (
            isinstance(key, tuple)
            and len(key) == 2
            and isinstance(key[0], str)
            and isinstance(key[1], int)
            and isinstance(value, str)
        ):
            normalized[(key[0], key[1])] = value
    return normalized


def resolve_well_id(
    slot_registry: Mapping[Tuple[str, int], str],
    box: str,
    slot_num: int,
) -> Optional[str]:
    """Resolve a well id for the given box/slot combination."""
    well_id = slot_registry.get((box, slot_num))
    if not well_id and isinstance(box, str) and box:
        well_id = slot_registry.get((box[0].upper(), slot_num))
    return well_id
