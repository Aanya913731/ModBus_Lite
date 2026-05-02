import threading
import time

class Poller(threading.Thread):
    def __init__(self, plc, get_active_reg, update_ui):
        super().__init__(daemon=True)
        self.plc = plc
        self.get_active_reg = get_active_reg
        self.update_ui = update_ui
        self.running = True

    def run(self):
        while self.running:
            r = self.get_active_reg()
            if not r:
                time.sleep(0.5); continue

            # Check/Restore Connection
            if not self.plc.is_connected():
                if not self.plc.connect():
                    r["quality"] = "OFFLINE"
                    r["value"] = "----"
                    r["raw_hex"] = "No Connection"
                    self.update_ui(r)
                    time.sleep(1.5) # Wait before retry
                    continue

            # Attempt Read
            res, raw_hex = self.plc.read_registers(r["unit"], r["address"], r["count"], r["reg_type"])
            
            if res is not None:
                if "COIL" in r["reg_type"] or "DISCRETE" in r["reg_type"]:
                    r["value"] = "ON" if res[0] else "OFF"
                else:
                    r["value"] = self.plc.decode(res, r["data_type"], r["order"])
                r["quality"] = "GOOD"
                r["raw_hex"] = raw_hex
            else:
                r["quality"] = "BAD (No Response)"
                r["value"] = "----"
                r["raw_hex"] = "Check Address/ID"
            
            self.update_ui(r)
            time.sleep(0.5) # Polling rate