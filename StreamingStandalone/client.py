# client.py
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime

import httpx
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

"""
client.py — Tkinter GUI client for Potentiostat temperature telemetry (SSE)

Overview
--------
This module implements a desktop GUI client that visualizes temperature telemetry
for multiple devices. It connects to a backend HTTP API, loads the latest known
temperature samples once on startup, and then subscribes to a Server-Sent Events
(SSE) stream to receive live updates.

The GUI provides:
- A table showing the latest temperature and timestamp per device
- A live-updating matplotlib line plot showing the recent temperature history
  for each device (sliding window / bounded buffer)
- A selectable update rate (Hz) that triggers a stream reconnect

Key Concepts / Architecture
---------------------------
The application is split into two main parts:

1) App (Tkinter main thread)
   - Owns the UI widgets (table, combobox, matplotlib canvas)
   - Maintains per-device state:
       * latest: last received sample per device
       * series: deque of recent (time, temperature) points per device
   - Periodically polls a thread-safe Queue using Tkinter's `after()` to
     integrate new samples into the UI (non-blocking GUI).

2) SSEClient (background thread)
   - Opens a streaming HTTP connection to the SSE endpoint
   - Parses SSE lines (event/data blocks) with a minimal custom parser
   - Emits parsed JSON payloads into a Queue for the GUI thread
   - Supports reconnect on demand (e.g., when update rate changes)
   - Stops cleanly when the global stop_event is set

Data Flow
---------
Startup:
    App -> GET /api/telemetry/temperature/latest
        -> applies each sample to table + plot buffers

Live updates:
    SSEClient -> GET /api/telemetry/temperature/stream?rate_hz=<rate>
        -> receives SSE events (event: temp + data: {...})
        -> json.loads(...) -> Queue.put(sample_dict)

    App (every ~50ms) -> drains Queue
        -> applies each sample
        -> redraws plot if anything changed

Backend API Expectations
------------------------
Base URL:
    API_BASE = "http://127.0.0.1:8000"

Endpoints used:
1) Latest samples (one-shot):
    GET {API_BASE}/api/telemetry/temperature/latest

   Expected JSON shape:
       {
         "samples": [
           {"device_id": 1, "temp_c": 23.456, "ts": "2026-01-30T12:34:56Z"},
           ...
         ]
       }

2) SSE stream (continuous):
    GET {API_BASE}/api/telemetry/temperature/stream?rate_hz=<float>
    Accept: text/event-stream

   Expected SSE event blocks (simplified):
       event: temp
       data: {"device_id": 1, "temp_c": 23.456, "ts": "..."}

       event: temp
       data: {...}

The client currently ignores SSE "id:" fields.

Device Handling
---------------
- DEVICE_IDS defines which devices are shown (default 1..10).
- For each device, a bounded deque holds the last N points (default 300).
- Time on the plot is shown as "relative seconds since the first point in that
  device's deque" to keep axes stable even if absolute timestamps differ.

Threading Notes / Safety
------------------------
- Tkinter UI updates must happen on the main thread. The SSEClient thread never
  touches widgets directly; it only writes parsed samples to `out_queue`.
- The GUI thread periodically polls `self.q` using `after(50, ...)` to update UI.
- Changing the rate triggers `SSEClient.reconnect()`, which breaks the current
  stream loop and reconnects using the updated parameter.

Configuration
-------------
- API_BASE: backend server URL
- DEVICE_IDS: list of device IDs displayed in table/plot
- rate_hz_var: update frequency (Hz per device) passed to the stream endpoint
- deque(maxlen=300): plot history length

Common Failure Modes / Troubleshooting
--------------------------------------
- If the table/plot stays empty:
    * backend not running or wrong API_BASE
    * SSE endpoint not returning `event: temp` blocks or invalid JSON
- If reconnect seems delayed:
    * reconnect waits until the streaming loop sees the reconnect flag while
      iterating lines; network stalls may delay processing.
- If timestamps look odd:
    * the plot uses local `time.time()` for x-axis, while the table displays
      the backend-provided `ts`.

Run
---
    python client.py

This starts the Tkinter GUI window and begins streaming immediately.
"""



API_BASE = "http://127.0.0.1:8000"  # oder IP

DEVICE_IDS = list(range(1, 11))

class SSEClient(threading.Thread):
    def __init__(self, out_queue: queue.Queue, rate_hz_var: tk.StringVar, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.rate_hz_var = rate_hz_var
        self.stop_event = stop_event
        self._reconnect_event = threading.Event()

    def reconnect(self):
        self._reconnect_event.set()

    def run(self):
        while not self.stop_event.is_set():
            rate_hz = self.rate_hz_var.get().strip() or "0.2"
            url = f"{API_BASE}/api/telemetry/temperature/stream?rate_hz={rate_hz}"

            try:
                with httpx.Client(timeout=None) as client:
                    with client.stream("GET", url, headers={"Accept": "text/event-stream"}) as r:
                        r.raise_for_status()

                        event = None
                        data_lines = []
                        # simple SSE parser
                        for line in r.iter_lines():
                            if self.stop_event.is_set() or self._reconnect_event.is_set():
                                break

                            if line is None:
                                continue
                            line = line.strip()

                            if line == "":
                                # dispatch
                                if event == "temp" and data_lines:
                                    data_str = "\n".join(data_lines)
                                    try:
                                        payload = json.loads(data_str)
                                        self.out_queue.put(payload)
                                    except json.JSONDecodeError:
                                        pass
                                # reset
                                event = None
                                data_lines = []
                                continue

                            if line.startswith("event:"):
                                event = line.split(":", 1)[1].strip()
                            elif line.startswith("data:"):
                                data_lines.append(line.split(":", 1)[1].strip())
                            # id: ignorieren wir erstmal

            except Exception as e:
                # kurze Pause bei Fehler, dann retry
                time.sleep(0.5)

            self._reconnect_event.clear()
            time.sleep(0.1)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Potentiostat Telemetry")
        self.geometry("1000x700")

        self.q = queue.Queue()
        self.stop_event = threading.Event()

        # UI State
        self.rate_hz_var = tk.StringVar(value="0.2")

        # pro Gerät: Label + Plot-Buffer (z.B. letzte 300 Punkte)
        self.latest = {d: None for d in DEVICE_IDS}
        self.series = {d: deque(maxlen=300) for d in DEVICE_IDS}  # (t, temp)

        self._build_ui()
        self._load_latest()

        # SSE thread
        self.sse = SSEClient(self.q, self.rate_hz_var, self.stop_event)
        self.sse.start()

        # Pump loop
        self.after(50, self._pump)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Update-Rate (Hz pro Gerät):").pack(side="left")
        rate = ttk.Combobox(top, textvariable=self.rate_hz_var, values=["0.2","1", "2", "5", "10", "20"], width=5, state="readonly")
        rate.pack(side="left", padx=6)

        def on_rate_change(*_):
            # Reconnect SSE mit neuer Rate
            self.sse.reconnect()

        self.rate_hz_var.trace_add("write", on_rate_change)

        # Table mit aktuellen Temperaturen
        mid = ttk.Frame(self)
        mid.pack(fill="x", padx=10, pady=10)

        self.tree = ttk.Treeview(mid, columns=("temp", "ts"), show="headings", height=10)
        self.tree.heading("temp", text="Temp (°C)")
        self.tree.heading("ts", text="Timestamp")
        self.tree.column("temp", width=120, anchor="e")
        self.tree.column("ts", width=260, anchor="w")
        self.tree.pack(fill="x")

        for d in DEVICE_IDS:
            self.tree.insert("", "end", iid=str(d), values=("-", "-"))

        # Plot
        fig = Figure(figsize=(9, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_title("Temperature")
        self.ax.set_xlabel("Time (relative)")
        self.ax.set_ylabel("°C")

        self.lines = {}
        for d in DEVICE_IDS:
            (ln,) = self.ax.plot([], [], label=f"Dev {d}")  # keine festen Farben gesetzt
            self.lines[d] = ln
        self.ax.legend(ncol=5, fontsize=8)

        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _load_latest(self):
        try:
            r = httpx.get(f"{API_BASE}/api/telemetry/temperature/latest", timeout=3.0)
            r.raise_for_status()
            data = r.json()["samples"]
            for s in data:
                self._apply_sample(s)
        except Exception:
            pass

    def _apply_sample(self, s: dict):
        d = int(s["device_id"])
        temp = float(s["temp_c"])
        ts = s["ts"]

        self.latest[d] = s
        # x-Achse: relative Zeit (Sekunden seit erster Probe in deque)
        now = time.time()
        self.series[d].append((now, temp))

        self.tree.set(str(d), "temp", f"{temp:.3f}")
        self.tree.set(str(d), "ts", ts)

    def _pump(self):
        changed = False
        while True:
            try:
                s = self.q.get_nowait()
            except queue.Empty:
                break
            self._apply_sample(s)
            changed = True

        if changed:
            self._redraw_plot()

        self.after(50, self._pump)

    def _redraw_plot(self):
        # relativieren, damit Achse stabil bleibt
        # (pro Gerät eigene deque; wir nutzen pro Gerät startzeit)
        for d in DEVICE_IDS:
            pts = list(self.series[d])
            if not pts:
                self.lines[d].set_data([], [])
                continue
            t0 = pts[0][0]
            xs = [p[0] - t0 for p in pts]
            ys = [p[1] for p in pts]
            self.lines[d].set_data(xs, ys)

        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def on_close(self):
        self.stop_event.set()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
