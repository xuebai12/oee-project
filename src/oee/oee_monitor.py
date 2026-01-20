import time
import sys
import os
import csv
from datetime import datetime

# --- 1. Core Configuration (核心配置) ---
# ⚠️ Arduino 端口 (如果连不上，代码会自动扫描并提示新端口)
SERIAL_PORT = '/dev/cu.usbmodem1401'  
BAUD_RATE = 9600
TARGET_STEPS = 30 
IDEAL_CYCLE_TIME = 8.5

# 尝试导入串口库
try:
    import serial
    import serial.tools.list_ports 
except ImportError:
    serial = None

# 模拟模式 (防止没有安装 pyserial 时报错)
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

# --- 🔥 Path Setup (核心修复：强制定位到用户目录) ---
# 1. 获取当前用户的主目录 (例如 /Users/baixue)
home_dir = os.path.expanduser("~")

# 2. 拼接完整的日志目录路径: /Users/baixue/oee-project/oee_logs
log_dir = os.path.join(home_dir, "oee-project", "oee_logs")

# 3. 尝试创建这个文件夹
try:
    os.makedirs(log_dir, exist_ok=True)
    print(f"📂 Log directory verified: {log_dir}")
except Exception as e:
    print(f"❌ Error creating directory: {e}")
    # 如果失败，退回到桌面 (双重保险)
    log_dir = os.path.join(home_dir, "Desktop")
    print(f"⚠️ Fallback to Desktop: {log_dir}")

# 初始化日志文件 (使用时间戳命名，防止覆盖)
log_filename = os.path.join(log_dir, f"OEE_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
print(f"📂 Logging started: {log_filename}")

# 立即写入表头，确保文件被创建
try:
    with open(log_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "State", "Prod_Time", "Setup_Time", "Down_Time", "Total_Count", "Defects", "A", "P", "Q", "OEE"])
        # 写入初始行
        writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "STOPPED", 0, 0, 0, 0, 0, 0, 0, 1, 0])
        f.flush()
        os.fsync(f.fileno())
except Exception as e:
    print(f"❌ Error creating file: {e}")

# --- Connection Logic ---
def connect_arduino():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"✅ Connected to: {SERIAL_PORT}")
        time.sleep(2)
        return ser
    except Exception as e:
        print(f"⚠️ Connection failed: {e}")
        print("🔍 Scanning ports...")
        if serial and hasattr(serial, 'tools'):
            ports = serial.tools.list_ports.comports()
            for p in ports:
                # 自动寻找名字里带 usb 的设备
                if 'usb' in p.device.lower():
                    print(f"👉 Found USB Device: {p.device}")
                    try:
                        return serial.Serial(p.device, BAUD_RATE, timeout=0.1)
                    except: pass
        # 如果找不到，提示用户
        print("❌ No Arduino found. Please check cable.")
        sys.exit()

def calculate_oee():
    total_planned = time.time() - start_time
    if total_planned < 1: return 0,0,0,0
    a = time_production / total_planned
    p = (total_count * IDEAL_CYCLE_TIME) / time_production if time_production > 0 else 0
    q = (total_count - defect_count) / total_count if total_count > 0 else 1
    return a, p, q, a*p*q

# --- Main Loop ---
ser = connect_arduino()
last_logged_state = None

try:
    while True:
        # 1. Read Serial
        if ser.in_waiting:
            try:
                line = ser.readline().decode().strip()
                if line in ["GREEN", "RED", "YELLOW"]: current_state = line
            except: pass
        
        # 2. Update Time
        now = time.time()
        elapsed = now - last_update_time
        last_update_time = now
        
        if current_state == "GREEN":
            time_production += elapsed
            expected = int(time_production / IDEAL_CYCLE_TIME)
            if expected > TARGET_STEPS: expected = TARGET_STEPS
            if expected > total_count: total_count = expected
        elif current_state == "YELLOW": time_setup += elapsed
        elif current_state == "RED": time_downtime += elapsed
        
        # 3. Log to CSV 
        if current_state != last_logged_state:
            a,p,q,o = calculate_oee()
            try:
                with open(log_filename, 'a', newline='') as f:
                    csv.writer(f).writerow([
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), current_state, 
                        f"{time_production:.1f}", f"{time_setup:.1f}", f"{time_downtime:.1f}", 
                        total_count, defect_count, f"{a*100:.1f}", f"{p*100:.1f}", f"{q*100:.1f}", f"{o*100:.1f}"
                    ])
                    f.flush()
                    os.fsync(f.fileno())
            except: pass
            
            last_logged_state = current_state
            
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n🛑 Finished.")
    if ser: ser.close()