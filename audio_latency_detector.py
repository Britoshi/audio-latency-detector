import tkinter as tk
from tkinter import ttk
import threading
import sounddevice as sd
import numpy as np

from detect_offset import (
    run_single_measurement,
    RUNS as DEFAULT_RUNS,
)

# ── Device helpers ───────────────────────────────────────────────────────────

def get_devices():
    devices = sd.query_devices()
    inputs  = [(i, d['name']) for i, d in enumerate(devices) if d['max_input_channels']  > 0]
    outputs = [(i, d['name']) for i, d in enumerate(devices) if d['max_output_channels'] > 0]
    return inputs, outputs


# ── Main window ──────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BT Offset Detector")
        self.resizable(False, False)
        self.configure(padx=24, pady=20)

        inputs, outputs = get_devices()

        # ── Device selectors ────────────────────────────────────────────────
        dev_frame = tk.LabelFrame(self, text="Devices", padx=12, pady=10)
        dev_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        tk.Label(dev_frame, text="Output (Loopback):").grid(row=0, column=0, sticky="w", pady=3)
        self.out_var = tk.StringVar()
        self.out_cb  = ttk.Combobox(dev_frame, textvariable=self.out_var, width=36, state="readonly")
        self.out_cb['values'] = [f"[{i}] {n}" for i, n in outputs]
        self.out_cb.grid(row=0, column=1, padx=(8, 0), pady=3)

        tk.Label(dev_frame, text="Input (Mic):").grid(row=1, column=0, sticky="w", pady=3)
        self.in_var = tk.StringVar()
        self.in_cb  = ttk.Combobox(dev_frame, textvariable=self.in_var, width=36, state="readonly")
        self.in_cb['values'] = [f"[{i}] {n}" for i, n in inputs]
        self.in_cb.grid(row=1, column=1, padx=(8, 0), pady=3)

        # pre-select last used or sensible defaults
        self._preselect(outputs, self.out_cb, ["Loopback", "Multi-Output"])
        self._preselect(inputs,  self.in_cb,  ["MacBook Pro Microphone", "Microphone"])

        # ── Runs spinner ─────────────────────────────────────────────────────
        opt_frame = tk.Frame(self)
        opt_frame.grid(row=1, column=0, sticky="w", pady=(0, 12))
        tk.Label(opt_frame, text="Runs:").pack(side="left")
        self.runs_var = tk.IntVar(value=DEFAULT_RUNS)
        tk.Spinbox(opt_frame, from_=1, to=20, textvariable=self.runs_var, width=4).pack(side="left", padx=(6, 0))

        # ── Run button ───────────────────────────────────────────────────────
        self.run_btn = tk.Button(
            self, text="▶  Run Detection", font=("", 13, "bold"),
            command=self._start, padx=12, pady=6,
            bg="#1a73e8", fg="white", activebackground="#1558b0", relief="flat", cursor="hand2"
        )
        self.run_btn.grid(row=2, column=0, sticky="ew", pady=(0, 14))

        # ── Progress ─────────────────────────────────────────────────────────
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, fg="gray").grid(row=4, column=0, sticky="w")

        # ── Results ──────────────────────────────────────────────────────────
        res_frame = tk.LabelFrame(self, text="Results", padx=12, pady=10)
        res_frame.grid(row=5, column=0, sticky="ew", pady=(12, 0))

        self.raw_var  = tk.StringVar(value="—")
        self.avg_var  = tk.StringVar(value="—")
        self.rec_var  = tk.StringVar(value="—")

        for row, label, var in [
            (0, "Raw (ms):",      self.raw_var),
            (1, "Average (ms):",  self.avg_var),
            (2, "Recommendation:", self.rec_var),
        ]:
            tk.Label(res_frame, text=label, anchor="w").grid(row=row, column=0, sticky="w", pady=2)
            tk.Label(res_frame, textvariable=var, anchor="w", font=("", 11, "bold"), wraplength=320).grid(
                row=row, column=1, sticky="w", padx=(8, 0), pady=2
            )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _preselect(self, device_list, cb, keywords):
        for kw in keywords:
            for i, (idx, name) in enumerate(device_list):
                if kw.lower() in name.lower():
                    cb.current(i)
                    return
        if device_list:
            cb.current(0)

    def _parse_device_index(self, value):
        return int(value.split("]")[0].replace("[", "").strip())

    # ── Run logic (background thread) ────────────────────────────────────────

    def _start(self):
        if not self.out_var.get() or not self.in_var.get():
            self.status_var.set("Select both devices first.")
            return

        self.run_btn.config(state="disabled")
        self.raw_var.set("—")
        self.avg_var.set("—")
        self.rec_var.set("—")
        self.progress_var.set(0)

        out_idx = self._parse_device_index(self.out_var.get())
        in_idx  = self._parse_device_index(self.in_var.get())
        runs    = self.runs_var.get()

        threading.Thread(target=self._run_detection, args=(out_idx, in_idx, runs), daemon=True).start()

    def _run_detection(self, out_idx, in_idx, runs):
        results = []
        for i in range(runs):
            self.after(0, self.status_var.set, f"Run {i+1}/{runs}…")
            offset = run_single_measurement(out_idx, in_idx, verbose=False)
            if offset is not None:
                results.append(offset)
            self.after(0, self.progress_var.set, (i + 1) / runs * 100)

        self.after(0, self._show_results, results, runs)

    def _show_results(self, results, runs):
        self.run_btn.config(state="normal")

        if not results:
            self.status_var.set("No valid readings — check mic placement.")
            return

        arr = np.array(results)

        # IQR outlier rejection
        q1, q3 = np.percentile(arr, [25, 75])
        iqr   = q3 - q1
        clean = arr[(arr >= q1 - 1.5*iqr) & (arr <= q3 + 1.5*iqr)]

        if len(clean) == 0:
            clean = arr  # fallback: no outlier removal if everything gets rejected

        avg = np.mean(clean)
        std = np.std(clean)

        raw_str = "  ".join(f"{r:+.1f}" for r in arr)
        self.raw_var.set(raw_str)
        self.avg_var.set(f"{avg:+.2f} ms  (σ {std:.2f})")

        if avg > 5:
            rec = f"Delay INTERNAL (L) by {avg:.0f} ms to match BT"
        elif avg < -5:
            rec = f"Delay BT (R) by {abs(avg):.0f} ms to match internal"
        else:
            rec = f"Within 5 ms — speakers are in sync ✓"

        self.rec_var.set(rec)
        self.status_var.set(f"Done — {len(clean)}/{runs} clean readings used")


if __name__ == "__main__":
    app = App()
    app.mainloop()