# app.py
import asyncio
import json
import math
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

DEVICE_IDS = list(range(1, 11))

@dataclass
class TemperatureSample:
    device_id: int
    ts: str          # ISO 8601
    temp_c: float
    seq: int

class LatestResponse(BaseModel):
    samples: List[TemperatureSample]

class MockPotentiostatSource:
    """
    Mockt 10 Geräte: Sinus + Drift + Noise + gelegentliche Dropouts.
    """
    def __init__(self, device_ids: List[int]) -> None:
        self.device_ids = device_ids
        self._seq_by_dev: Dict[int, int] = {d: 0 for d in device_ids}
        self._base_by_dev: Dict[int, float] = {d: 25.0 + d * 0.3 for d in device_ids}
        self._t0 = time.time()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def generate_one(self, device_id: int) -> Optional[TemperatureSample]:
        # Simuliere seltene Dropouts
        if random.random() < 0.01:
            return None

        t = time.time() - self._t0
        base = self._base_by_dev[device_id]

        # langsame Welle + kleines Rauschen + minimale Drift
        temp = base + 0.8 * math.sin(t / 15.0 + device_id) + random.gauss(0, 0.03)
        self._base_by_dev[device_id] += random.gauss(0, 0.0005)

        self._seq_by_dev[device_id] += 1
        return TemperatureSample(
            device_id=device_id,
            ts=self._now_iso(),
            temp_c=round(temp, 3),
            seq=self._seq_by_dev[device_id],
        )

source = MockPotentiostatSource(DEVICE_IDS)

# In-Memory latest cache (für /latest)
latest_by_dev: Dict[int, TemperatureSample] = {}

@app.get("/api/telemetry/temperature/latest")
def get_latest():
    # Falls noch leer, einmal initial befüllen
    for d in DEVICE_IDS:
        if d not in latest_by_dev:
            s = source.generate_one(d)
            if s:
                latest_by_dev[d] = s
    return {"samples": [asdict(latest_by_dev[d]) for d in DEVICE_IDS if d in latest_by_dev]}

def sse_format(event: str, data_obj, event_id: Optional[str] = None) -> str:
    # SSE: einzelne Message endet mit \n\n
    msg = ""
    if event_id is not None:
        msg += f"id: {event_id}\n"
    msg += f"event: {event}\n"
    msg += "data: " + json.dumps(data_obj, separators=(",", ":")) + "\n\n"
    return msg

@app.get("/api/telemetry/temperature/stream")
async def temperature_stream(rate_hz: float = Query(2.0, ge=0.2, le=20.0)):
    """
    Eine SSE-Verbindung, die alle Geräte zyklisch sendet.
    rate_hz = Samples pro Sekunde pro Gerät (ungefähr).
    """
    interval = 1.0 / rate_hz
    last_ping = time.time()

    async def gen():
        # Initial: optional direkt einmal alles senden
        for d in DEVICE_IDS:
            s = source.generate_one(d)
            if s:
                latest_by_dev[d] = s
                yield sse_format("temp", asdict(s), event_id=f"{d}:{s.seq}")

        while True:
            start = time.time()
            for d in DEVICE_IDS:
                s = source.generate_one(d)
                if s:
                    latest_by_dev[d] = s
                    yield sse_format("temp", asdict(s), event_id=f"{d}:{s.seq}")

            # Heartbeat alle 15s
            if time.time() - last_ping >= 15:
                last_ping = time.time()
                yield sse_format("ping", {"ts": datetime.now(timezone.utc).isoformat()})

            # Timing: ungefähr rate_hz pro device
            elapsed = time.time() - start
            sleep_for = max(0.0, interval - elapsed)
            await asyncio.sleep(sleep_for)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # NGINX: "X-Accel-Buffering": "no"  (falls du hinter nginx bist)
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
