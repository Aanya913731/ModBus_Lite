import threading
import struct
import math
from pymodbus.client.sync import ModbusTcpClient

class PLCClient:
    def __init__(self, ip, port, base_mode=1):
        self.ip = ip
        self.port = int(port)
        self.base_mode = int(base_mode)
        self.client = None
        self._connected = False
        self.lock = threading.Lock()

    def connect(self):
        try:
            if self.client: self.client.close()
            # Short timeout (0.5s) stops the "one minute" hang
            self.client = ModbusTcpClient(self.ip, port=self.port, timeout=0.5)
            self._connected = self.client.connect()
            return self._connected
        except:
            return False

    def close(self):
        with self.lock:
            if self.client: self.client.close()
        self._connected = False

    def is_connected(self):
        return self._connected

    def _map_address(self, reg_type, address):
        try:
            if "HOLDING" in reg_type: return max(0, address - (40000 + self.base_mode))
            if "INPUT" in reg_type:   return max(0, address - (30000 + self.base_mode))
            if "COIL" in reg_type:    return max(0, address - self.base_mode)
            if "DISCRETE" in reg_type: return max(0, address - (10000 + self.base_mode))
            return address
        except: return 0

    def read_registers(self, unit, address, count, reg_type):
        if not self._connected: return None, None
        addr = self._map_address(reg_type, address)
        try:
            with self.lock:
                if "HOLDING" in reg_type: rr = self.client.read_holding_registers(addr, count, unit=unit)
                elif "INPUT" in reg_type: rr = self.client.read_input_registers(addr, count, unit=unit)
                elif "COIL" in reg_type:  rr = self.client.read_coils(addr, count, unit=unit)
                elif "DISCRETE" in reg_type: rr = self.client.read_discrete_inputs(addr, count, unit=unit)
                else: return None, None
            
            if rr and not rr.isError():
                if hasattr(rr, "registers"):
                    raw_hex = " ".join([f"{x:04X}" for x in rr.registers])
                    return rr.registers, raw_hex
                else:
                    raw_hex = str(rr.bits[:count])
                    return rr.bits, raw_hex
        except:
            self._connected = False
        return None, None

    def decode(self, regs, dtype, order):
        if not regs or not isinstance(regs, list): return "----"
        raw = bytearray()
        for r in regs: raw.extend(struct.pack(">H", r))
        if order == "LSR First (CDAB)" and len(raw) >= 4:
            raw[0:4] = raw[2:4] + raw[0:2]
        try:
            if dtype == "FLOAT":
                v = struct.unpack(">f", raw[:4])[0]
                return round(v, 4) if not (math.isnan(v) or math.isinf(v)) else 0.0
            if dtype == "INT32": return struct.unpack(">i", raw[:4])[0]
            if dtype == "UINT32": return struct.unpack(">I", raw[:4])[0]
            if dtype == "INT16": return struct.unpack(">h", raw[:2])[0]
            if dtype == "UINT16": return struct.unpack(">H", raw[:2])[0]
            if dtype == "DOUBLE": return round(struct.unpack(">d", raw[:8])[0], 6)
        except: return "Error"