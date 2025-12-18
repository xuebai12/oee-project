import time
import sys
import os
import csv
from datetime import datetime

# --- 1. Core Configuration ---
SERIAL_PORT = '/dev/cu.usbmodem1401'  # 默认端口
BAUD_RATE = 9600
TARGET_STEPS = 30 
IDEAL_CYCLE_TIME = 20.0

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

# --- Variables ---
current_state = "STOPPED"
start_time = time.time()
time_production = 0.0
time_setup = 0.0
time_downtime = 0.0
last_update_time = time.time()
total_count = 0  
good_count = 0
defect_count = 0 

# --- Log File Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
log_dir = os.path.join(project_root, "oee_logs")
os.makedirs(log_dir, exist_ok=True)

log_filename = os.path.join(log_dir, f"OEE_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
print(f"📂 Log file initialized at: {log_filename}")

# Initialize CSV with Header
try:
    with open(log_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", "State", 
            "Production_Time(s)", "Setup_Time(s)", "Downtime_Time(s)", 
            "Total_Count", "Defect_Count", 
            "Availability(%)", "Performance(%)", "Quality(%)", "OEE(%)"
        ])
        writer.writerow([
            datetime.now().strftime('%H:%M:%S'), "STOPPED", 
            0, 0, 0, 0, 0, 0, 0, 0, 0
        ])
        f.flush() # Force write
        os.fsync(f.fileno())
except Exception as e:
    print(f"❌ Error creating log file: {e}")

# --- Connection Logic (Robust) ---
def get_serial_connection():
    """尝试连接 Arduino"""
    global SERIAL_PORT
    first_attempt = True
    while True:
        try:
            if first_attempt:
                print(f"🔌 Connecting to {SERIAL_PORT}...")
            
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
            print(f"✅ Connected!")
            time.sleep(2)
            return ser
            
        except Exception:
            # 连接失败，开始扫描
            if first_attempt:
                print(f"⚠️ Connection failed. Searching for Arduino...")
                first_attempt = False
            
            # 尝试自动寻找
            if serial and hasattr(serial, 'tools'):
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    # 只要名字里带 'usb'，就试着连一下
                    if 'usb' in p.device.lower():
                        try:
                            ser = serial.Serial(p.device, BAUD_RATE, timeout=0.1)
                            SERIAL_PORT = p.device
                            print(f"\n✅ Auto-Connected to new port: {SERIAL_PORT}")
                            time.sleep(2)
                            return ser
                        except: pass
            
            # 如果没找到，安静地等待 5 秒再试，不刷屏
            time.sleep(5) 
def calculate_oee():
    total_planned = time.time() - start_time
    if total_planned < 1: return 0,0,0,0
    a = time_production / total_planned
    p = (total_count * IDEAL_CYCLE_TIME) / time_production if time_production > 0 else 0
    q = (total_count - defect_count) / total_count if total_count > 0 else 1
    return a, p, q, a*p*q

# --- Main Loop ---
ser = get_serial_connection() # Use robust connection
last_logged_state = None
last_log_time = time.time()

try:
    while True:
        # 1. Read Serial (with error handling for disconnection)
        try:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                if line in ["GREEN", "RED", "YELLOW"]: 
                    current_state = line
        except (OSError, serial.SerialException):
            print("\n❌ Connection lost! Reconnecting...")
            ser.close()
            ser = get_serial_connection() # Reconnect without killing script
            continue
        
        # 2. Update Time
        now = time.time()
        elapsed = now - last_update_time
        last_update_time = now
        
        if current_state == "GREEN":
            time_production += elapsed
            expected = int(time_production / IDEAL_CYCLE_TIME)
                
            # 🔥 修改点：限制最大产量为 TARGET_STEPS (30)
            if expected > TARGET_STEPS:
                expected = TARGET_STEPS
            
            if expected > total_count: total_count = expected
            if expected > total_count: total_count = expected
        elif current_state == "YELLOW": time_setup += elapsed
        elif current_state == "RED": time_downtime += elapsed
        
        # 3. Hybrid Logging
        state_changed = (current_state != last_logged_state)
        heartbeat_due = (time.time() - last_log_time >= 1.0)
        
        if state_changed or heartbeat_due:
            a,p,q,o = calculate_oee()
            
            if state_changed:
                print(f"🔄 State Change: {last_logged_state} -> {current_state}")
            
            try:
                with open(log_filename, 'a', newline='') as f:
                    csv.writer(f).writerow([
                        datetime.now().strftime('%H:%M:%S'), 
                        current_state, 
                        f"{time_production:.1f}", 
                        f"{time_setup:.1f}", 
                        f"{time_downtime:.1f}", 
                        total_count, 
                        defect_count, 
                        f"{a*100:.1f}", 
                        f"{p*100:.1f}", 
                        f"{q*100:.1f}", 
                        f"{o*100:.1f}"
                    ])
                    # 🔥 CRITICAL: Force write to disk immediately
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                print(f"⚠️ Log Error: {e}")

            last_logged_state = current_state
            last_log_time = time.time()
            
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n🛑 Finished.")
    if ser: ser.close()