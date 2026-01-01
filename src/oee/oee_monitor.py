import time
import sys
import os
import sqlite3
import yaml
from datetime import datetime

# --- 1. Load Configuration ---
def load_config():
    config_path = os.path.join(os.getcwd(), "config.yaml")
    if not os.path.exists(config_path):
        # Default config if file missing
        return {
            'serial': {'port': '/dev/cu.usbmodem1401', 'baud_rate': 9600},
            'production': {'target_steps': 30, 'ideal_cycle_time': 20.0},
            'database': {'path': 'oee_data.db'}
        }
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

CONFIG = load_config()

# Try to import serial
try:
    import serial
    import serial.tools.list_ports 
except ImportError:
    serial = None

# Mock Serial
if serial is None:
    class _FakeSerial:
        def __init__(self, *args, **kwargs): print("⚠️ Simulation Mode")
        @property
        def in_waiting(self): return 0
        def readline(self): time.sleep(0.1); return b""
        def close(self): pass
    class _SerialModule: Serial = _FakeSerial
    serial = _SerialModule()

class OEEMonitor:
    def __init__(self):
        self.config = CONFIG
        self.port = self.config['serial']['port']
        self.baud = self.config['serial']['baud_rate']
        self.target_steps = self.config['production']['target_steps']
        self.ideal_cycle_time = self.config['production']['ideal_cycle_time']
        self.db_path = self.config['database']['path']
        
        self.current_state = "STOPPED"
        self.start_time = time.time()
        self.time_production = 0.0
        self.time_setup = 0.0
        self.time_downtime = 0.0
        self.last_update_time = time.time()
        self.total_count = 0  
        self.defect_count = 0 
        
        self.init_db()
        self.ser = self.get_serial_connection()

    def init_db(self):
        """Initialize SQLite database for OEE data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oee_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                state TEXT,
                prod_time REAL,
                setup_time REAL,
                down_time REAL,
                total_count INTEGER,
                defect_count INTEGER,
                availability REAL,
                performance REAL,
                quality REAL,
                oee REAL
            )
        ''')
        conn.commit()
        conn.close()
        print(f"📂 Database initialized at: {self.db_path}")

    def get_serial_connection(self):
        """Robust serial connection logic."""
        first_attempt = True
        while True:
            try:
                if first_attempt:
                    print(f"🔌 Connecting to {self.port}...")
                
                ser = serial.Serial(self.port, self.baud, timeout=0.1)
                print(f"✅ Connected!")
                time.sleep(2)
                return ser
                
            except Exception:
                if first_attempt:
                    print(f"⚠️ Connection failed. Searching for Arduino...")
                    first_attempt = False
                
                if serial and hasattr(serial, 'tools'):
                    ports = serial.tools.list_ports.comports()
                    for p in ports:
                        if 'usb' in p.device.lower():
                            try:
                                ser = serial.Serial(p.device, self.baud, timeout=0.1)
                                self.port = p.device
                                print(f"\n✅ Auto-Connected to new port: {self.port}")
                                time.sleep(2)
                                return ser
                            except: pass
                time.sleep(5) 

    def calculate_oee(self):
        total_planned = time.time() - self.start_time
        if total_planned < 1: return 0, 0, 0, 0
        a = self.time_production / total_planned
        p = (self.total_count * self.ideal_cycle_time) / self.time_production if self.time_production > 0 else 0
        q = (self.total_count - self.defect_count) / self.total_count if self.total_count > 0 else 1
        return a, p, q, a*p*q

    def log_to_db(self):
        """Log current metrics to SQLite."""
        a, p, q, o = self.calculate_oee()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO oee_logs (
                timestamp, state, prod_time, setup_time, down_time, 
                total_count, defect_count, availability, performance, quality, oee
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%H:%M:%S'),
            self.current_state,
            round(self.time_production, 1),
            round(self.time_setup, 1),
            round(self.time_downtime, 1),
            self.total_count,
            self.defect_count,
            round(a * 100, 1),
            round(p * 100, 1),
            round(q * 100, 1),
            round(o * 100, 1)
        ))
        conn.commit()
        conn.close()

    def run(self):
        last_logged_state = None
        last_log_time = time.time()
        
        try:
            while True:
                # 1. Read Serial
                try:
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode().strip()
                        if line in ["GREEN", "RED", "YELLOW"]: 
                            self.current_state = line
                except (OSError, serial.SerialException):
                    print("\n❌ Connection lost! Reconnecting...")
                    self.ser.close()
                    self.ser = self.get_serial_connection()
                    continue
                
                # 2. Update Time
                now = time.time()
                elapsed = now - self.last_update_time
                self.last_update_time = now
                
                if self.current_state == "GREEN":
                    self.time_production += elapsed
                    expected = int(self.time_production / self.ideal_cycle_time)
                    if expected > self.target_steps:
                        expected = self.target_steps
                    if expected > self.total_count: 
                        self.total_count = expected
                elif self.current_state == "YELLOW": 
                    self.time_setup += elapsed
                elif self.current_state == "RED": 
                    self.time_downtime += elapsed
                
                # 3. Logging
                state_changed = (self.current_state != last_logged_state)
                heartbeat_due = (time.time() - last_log_time >= 1.0)
                
                if state_changed or heartbeat_due:
                    if state_changed:
                        print(f"🔄 State Change: {last_logged_state} -> {self.current_state}")
                    
                    try:
                        self.log_to_db()
                    except Exception as e:
                        print(f"⚠️ Log Error: {e}")

                    last_logged_state = self.current_state
                    last_log_time = time.time()
                    
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n🛑 Finished.")
            if self.ser: self.ser.close()

if __name__ == "__main__":
    monitor = OEEMonitor()
    monitor.run()