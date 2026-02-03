from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from seva.domain.device_activity import DeviceActivitySnapshot, SlotActivityEntry
from seva.domain.mapping import build_slot_registry, extract_slot_labels, parse_slot_number, resolve_well_id
from seva.domain.ports import DevicePort
class PollDeviceStatus:
    def __init__(self, device_port: DevicePort) -> None:
        self.device_port = device_port
        self._slot_registry: Dict[Tuple[str, int], str] = {}
        self._boxes: List[str] = []

    def __call__(self, boxes: Sequence[str]) -> DeviceActivitySnapshot:
        box_list = [str(box) for box in boxes if str(box).strip()]
        if box_list != self._boxes or not self._slot_registry:
            self._rebuild_registry(box_list)

        entries: List[SlotActivityEntry] = []
        for box in box_list:
            statuses = self.device_port.list_device_status(box)
            for status in statuses:
                slot_label = str(status.get("slot") or "").strip()
                if not slot_label:
                    continue
                slot_num = parse_slot_number(slot_label)
                well_id = resolve_well_id(self._slot_registry, box, slot_num)
                if not well_id:
                    continue
                raw_status = str(status.get("status") or "idle")
                entries.append(
                    SlotActivityEntry(
                        well_id=well_id,
                        status=self._normalize_status(raw_status),
                    )
                )

        return DeviceActivitySnapshot(entries=tuple(entries))

    def _rebuild_registry(self, boxes: Sequence[str]) -> None:
        slots_by_box: Dict[str, List[str]] = {}
        for box in boxes:
            payload = self.device_port.list_devices(box)
            slots_by_box[box] = extract_slot_labels(payload)
        _, slot_registry = build_slot_registry(boxes, slots_by_box)
        self._slot_registry = dict(slot_registry)
        self._boxes = list(boxes)

    def _normalize_status(self, raw_status: str) -> str:
        key = (raw_status or "").strip().lower()
        if key in {"idle", "done"}:
            return "Idle"
        if key in {"failed", "error"}:
            return "Error"
        if key in {"cancelled", "canceled"}:
            return "Canceled"
        if key == "queued":
            return "Queued"
        if key == "running":
            return "Running"
        return key.title() if key else "Idle"


__all__ = ["DeviceActivitySnapshot", "PollDeviceStatus", "SlotActivityEntry"]
