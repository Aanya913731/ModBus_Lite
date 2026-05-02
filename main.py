import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import csv
from datetime import datetime

# --- PACKING FIX FOR PYINSTALLER ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    sys.path.append(resource_path(''))

try:
    from module.modbus_client import PLCClient
    from module.poller import Poller
except ImportError as e:
    print(f"Import Error: {e}")

class ModScanApp:
    def __init__(self, root):
        self.root = root
        root.title("Python ModScan Pro - Full Engineering Suite")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.plc, self.poller, self.active_reg = None, None, None
        self.last_saved_value = None 

        # --- Step 1: Connection & Device Info ---
        top = ttk.LabelFrame(root, text="Step 1: Connection & Device Info")
        top.pack(fill="x", padx=10, pady=5)
        r1 = ttk.Frame(top); r1.pack(fill="x", pady=5)
        ttk.Label(r1, text="IP:").pack(side="left", padx=5)
        self.ip = ttk.Entry(r1, width=15); self.ip.insert(0, "127.0.0.1"); self.ip.pack(side="left")
        ttk.Label(r1, text="Port:").pack(side="left", padx=5)
        self.port = ttk.Entry(r1, width=6); self.port.insert(0, "502"); self.port.pack(side="left")
        ttk.Label(r1, text="Unit ID:").pack(side="left", padx=5)
        self.uid = ttk.Entry(r1, width=5); self.uid.insert(0, "1"); self.uid.pack(side="left")
        ttk.Label(r1, text="Base:").pack(side="left", padx=5)
        self.base = ttk.Combobox(r1, values=["0", "1"], state="readonly", width=3); self.base.set("1"); self.base.pack(side="left")

        # --- Step 2: Data Definition ---
        cfg = ttk.LabelFrame(root, text="Step 2: Data Definition")
        cfg.pack(fill="x", padx=10, pady=5)
        r2 = ttk.Frame(cfg); r2.pack(fill="x", pady=5)
        self.reg_type = ttk.Combobox(r2, values=["HOLDING (4x)", "INPUT (3x)", "COIL (0x)", "DISCRETE (1x)"],state="readonly", width=15)
        self.reg_type.set("HOLDING (4x)"); self.reg_type.pack(side="left", padx=5)
        self.data_type = ttk.Combobox(r2, values=["FLOAT", "INT16", "UINT16", "INT32", "UINT32", "DOUBLE"], state="readonly", width=10)
        self.data_type.set("FLOAT"); self.data_type.pack(side="left", padx=5)
        self.order = ttk.Combobox(r2, values=["MSR First (ABCD)", "LSR First (CDAB)"], state="readonly", width=18)
        self.order.set("MSR First (ABCD)"); self.order.pack(side="left", padx=5)
        ttk.Label(r2, text="Addr:").pack(side="left", padx=5)
        self.addr = ttk.Entry(r2, width=8); self.addr.insert(0, "40001"); self.addr.pack(side="left")

        # LIVE BINDINGS: Updates poller while it's running
        self.reg_type.bind("<<ComboboxSelected>>", self.sync_params)
        self.data_type.bind("<<ComboboxSelected>>", self.sync_params)
        self.order.bind("<<ComboboxSelected>>", self.sync_params)
        self.addr.bind("<KeyRelease>", self.sync_params)

        # --- Controls ---
        ctrl = ttk.Frame(root); ctrl.pack(fill="x", padx=10)
        self.btn_start = ttk.Button(ctrl, text="START SCANNING", command=self.start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=5)
        self.btn_stop = ttk.Button(ctrl, text="STOP SCANNING", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=5)

        # --- Live Monitor & Traffic ---
        mid = ttk.LabelFrame(root, text="Live Monitor & Traffic")
        mid.pack(fill="x", padx=10, pady=10)
        self.live_val = tk.Label(mid, text="----", font=("Arial", 40, "bold"), fg="blue")
        self.live_val.pack()
        self.traffic_label = tk.Label(mid, text="Raw Hex: ----", font=("Courier", 10), fg="darkgreen")
        self.traffic_label.pack(pady=5)
        self.status = tk.Label(mid, text="Status: Ready", fg="gray")
        self.status.pack()

        # --- Session History ---
        hist = ttk.LabelFrame(root, text="Session History (Auto-Records Changes)")
        hist.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree = ttk.Treeview(hist, columns=("IP", "Addr", "Val", "Type", "Time"), show="headings", height=8)
        for c in ("IP", "Addr", "Val", "Type", "Time"):
            self.tree.heading(c, text=c); self.tree.column(c, anchor="center")
        self.tree.pack(fill="both", expand=True)

    def sync_params(self, event=None):
        if self.active_reg:
            try:
                dtype = self.data_type.get()
                self.active_reg.update({
                    "reg_type": self.reg_type.get(),
                    "data_type": dtype,
                    "order": self.order.get(),
                    "address": int(self.addr.get()),
                    "count": {"DOUBLE": 4, "FLOAT": 2, "INT32": 2, "UINT32": 2}.get(dtype, 1)
                })
            except: pass # Ignore partial address typing errors

    def on_closing(self):
        if self.tree.get_children():
            response = messagebox.askyesnocancel("Exit", "Save history to CSV before exiting?")
            if response is True:
                filename = datetime.now().strftime("Modbus_History_%Y%m%d_%H%M%S.csv")
                try:
                    with open(filename, mode='w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["IP", "Address", "Value", "Type", "Time"])
                        for item in self.tree.get_children():
                            writer.writerow(self.tree.item(item)['values'])
                    messagebox.showinfo("Saved", f"Exported to {filename}")
                except: pass
            elif response is None: return
        if self.poller: self.poller.running = False
        self.root.destroy()

    def start(self):
        self.last_saved_value = None
        dtype = self.data_type.get()
        self.active_reg = {
            "ip": self.ip.get(), "unit": int(self.uid.get()), "reg_type": self.reg_type.get(),
            "data_type": dtype, "order": self.order.get(), "address": int(self.addr.get()),
            "count": {"DOUBLE": 4, "FLOAT": 2, "INT32": 2, "UINT32": 2}.get(dtype, 1),
            "value": "----", "quality": "INIT", "raw_hex": ""
        }
        self.plc = PLCClient(self.ip.get(), self.port.get(), self.base.get())
        self.poller = Poller(self.plc, lambda: self.active_reg, self.refresh)
        self.poller.start()
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal")

    def stop(self):
        if self.poller: self.poller.running = False; self.poller = None
        if self.plc: self.plc.close(); self.plc = None
        self.live_val.config(text="----", fg="blue")
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")

    def refresh(self, r):
        new_val = str(r["value"])
        quality = r["quality"]
        color = "green" if quality == "GOOD" else "red"
        
        self.live_val.config(text=new_val, fg=color)
        self.traffic_label.config(text=f"Raw Hex: {r.get('raw_hex', '----')}")
        self.status.config(text=f"Status: {quality} | IP: {r['ip']}", fg=color)

        if quality == "GOOD" and new_val != "----" and new_val != self.last_saved_value:
            self.last_saved_value = new_val
            self.tree.insert("", 0, values=(r["ip"], r["address"], new_val, r["data_type"], datetime.now().strftime("%H:%M:%S")))

if __name__ == "__main__":
    root = tk.Tk(); root.geometry("950x800")
    ModScanApp(root); root.mainloop()