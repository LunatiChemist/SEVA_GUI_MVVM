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
        rate = ttk.Combobox(top, textvariable=self.rate_hz_var, values=["0.2","1", "2", "5", "10"], width=5, state="readonly")
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
        self.ax.set_title("Temperaturverlauf (letzte Punkte)")
        self.ax.set_xlabel("Zeit (relativ)")
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
