# 🏭 OEE Project (Overall Equipment Effectiveness)

A real-time manufacturing dashboard and KPI analysis system that monitors production efficiency through Arduino hardware integration and provides comprehensive OEE (Overall Equipment Effectiveness) metrics visualization.

## 📺 Demo
[![Watch the video](https://img.youtube.com/vi/dOijTcQgJTE/maxresdefault.jpg)](https://youtu.be/dOijTcQgJTE)

---

## 📋 Table of Contents
- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [OEE Metrics Explained](#-oee-metrics-explained)
- [Development](#-development)

---

## 🎯 Overview

This project provides a complete solution for monitoring and analyzing manufacturing production lines in real-time. It consists of two main components:

1. **OEE Monitor** (`oee_monitor.py`) - Collects real-time data from Arduino hardware via serial communication
2. **Dashboard** (`dashboardv1.py`) - Visualizes production metrics using an interactive Streamlit web interface

The system tracks three production states (Production/Setup/Downtime) and calculates key performance indicators including Availability, Performance, Quality, and overall OEE.

---

## ✨ Features

### Real-Time Monitoring
- **Arduino Integration**: Reads production states via serial communication (GREEN/YELLOW/RED signals)
- **Live Data Collection**: Continuous monitoring with automatic CSV logging
- **State Tracking**: Monitors Production, Setup, and Downtime states

### Interactive Dashboard
- **Live View**: Real-time metrics with auto-refresh capability
- **Historical Analysis**: Review past production sessions
- **Session Management**: End sessions with defect input and generate final reports
- **Visual Analytics**: 
  - OEE component breakdown (A × P × Q)
  - Time distribution pie charts
  - Trend analysis charts
  - State change timeline logs
  - ETA predictions for production targets

### Data Management
- **Automatic Logging**: Timestamped CSV files for each session
- **Session History**: Browse and analyze historical production runs
- **Configurable Settings**: YAML-based configuration for easy customization

---

## 📁 Project Structure

```
oee-project/
├── src/
│   └── oee/
│       ├── __init__.py
│       ├── oee_monitor.py      # Arduino data collection & OEE calculation
│       └── dashboardv1.py      # Streamlit dashboard UI
├── oee_logs/                   # CSV log files (auto-generated)
│   └── OEE_Log_YYYYMMDD_HHMMSS.csv
├── tests/
│   └── test_basic.py           # Basic test suite
├── config.yaml                 # Production configuration
├── pyproject.toml              # Python dependencies & project metadata
├── main.py                     # Entry point (placeholder)
├── Dockerfile                  # Docker containerization
├── docker-compose.yml          # Docker orchestration
└── README.md                   # This file
```

### Key Files Explained

#### `src/oee/oee_monitor.py`
- Connects to Arduino via serial port
- Reads production state signals (GREEN/RED/YELLOW)
- Calculates time spent in each state
- Computes OEE metrics (Availability, Performance, Quality)
- Logs data to timestamped CSV files
- Includes fallback simulation mode if Arduino is not connected

#### `src/oee/dashboardv1.py`
- Streamlit-based web dashboard
- Displays real-time OEE metrics with large visual cards
- Provides historical session viewer
- Allows session management (end session, input defects)
- Generates trend charts and time breakdowns
- Supports both live and historical data views

#### `config.yaml`
- Serial port configuration for Arduino
- Production targets (target steps, ideal cycle time)
- Database path settings

#### `pyproject.toml`
- Python package configuration
- Dependencies: `streamlit`, `plotly`, `pyserial`, `PyYAML`
- Development tools: `pytest`, `ruff`, `black`

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Arduino       │  Sends state signals (GREEN/YELLOW/RED)
│   Hardware      │  via USB Serial
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│   oee_monitor.py                        │
│   • Reads serial data                   │
│   • Tracks state changes                │
│   • Calculates OEE metrics              │
│   • Writes to CSV logs                  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│   oee_logs/OEE_Log_*.csv                │
│   • Timestamped production data         │
│   • State changes & metrics             │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│   dashboardv1.py (Streamlit)            │
│   • Reads CSV files                     │
│   • Displays live/historical data       │
│   • Interactive visualizations          │
│   • Session management                  │
└─────────────────────────────────────────┘
```

---

## 🛠 Installation

### Prerequisites
- **Python** 3.12 or higher
- **macOS** (tested on Mac, adaptable to Linux/Windows)
- **Arduino** (optional, has simulation mode)

### Install UV Package Manager
We use `uv` for fast, reliable Python package management:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone the Repository
```bash
git clone https://github.com/xuebai12/oee-project.git
cd oee-project
```

### Install Dependencies
Dependencies are automatically installed when running commands with `uv run`:

```bash
uv sync  # Optional: pre-install all dependencies
```

---

## 🚀 Usage

### 1. Configure Your Setup
Edit `config.yaml` to match your hardware configuration:

```yaml
serial:
  port: "/dev/cu.usbmodem12401"  # Your Arduino port
  baud_rate: 9600

production:
  target_steps: 30                # Production target
  ideal_cycle_time: 8.5           # Seconds per unit
```

### 2. Run the OEE Monitor (Data Collection)
Start collecting data from Arduino:

```bash
uv run python src/oee/oee_monitor.py
```

**What it does:**
- Connects to Arduino via serial port
- Monitors production states in real-time
- Creates timestamped CSV log files in `oee_logs/`
- Runs continuously until stopped (Ctrl+C)

**Note:** If Arduino is not connected, it runs in simulation mode.

### 3. Run the Dashboard (Visualization)
Launch the web dashboard:

```bash
uv run streamlit run src/oee/dashboardv1.py
```

**What it does:**
- Opens a web browser at `http://localhost:8501`
- Displays real-time OEE metrics
- Auto-refreshes every 5 seconds
- Allows browsing historical sessions

### 4. Using the Dashboard

#### Live Mode
- View current production session metrics
- Monitor OEE components (A, P, Q)
- Track production progress and ETA
- End session and input defect counts

#### Historical Mode
- Select past sessions from sidebar
- Review final production reports
- Analyze time breakdowns and trends
- Compare performance across sessions

---

## ⚙️ Configuration

### Serial Port Configuration
Find your Arduino port:

```bash
# macOS/Linux
ls /dev/cu.*

# The monitor script will auto-detect USB devices if connection fails
```

### Production Settings
- **target_steps**: Total units to produce in a session
- **ideal_cycle_time**: Expected time (seconds) to produce one unit

### Database (Future Feature)
- Currently uses CSV files
- Database path reserved for future SQLite integration

---

## 📊 OEE Metrics Explained

OEE (Overall Equipment Effectiveness) = **A × P × Q**

### Availability (A)
```
A = Production Time / Total Planned Time
```
Measures the percentage of time the equipment is actually producing.

### Performance (P)
```
P = (Total Count × Ideal Cycle Time) / Production Time
```
Measures how fast the equipment is producing compared to ideal speed.

### Quality (Q)
```
Q = (Total Count - Defects) / Total Count
```
Measures the percentage of good units produced.

### Overall OEE
```
OEE = A × P × Q × 100%
```
World-class OEE is typically **85%** or higher.

---

## 🧪 Development

### Running Tests
```bash
uv run pytest
```

### Code Formatting
```bash
uv run black src/
```

### Linting
```bash
uv run ruff check src/
```

### Docker Deployment
```bash
docker-compose up --build
```

---

## 📝 CSV Log Format

Each session creates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `Timestamp` | Date and time of the record |
| `State` | Current state (GREEN/YELLOW/RED/STOPPED) |
| `Prod_Time` | Cumulative production time (seconds) |
| `Setup_Time` | Cumulative setup time (seconds) |
| `Down_Time` | Cumulative downtime (seconds) |
| `Total_Count` | Total units produced |
| `Defects` | Number of defective units |
| `A` | Availability percentage |
| `P` | Performance percentage |
| `Q` | Quality percentage |
| `OEE` | Overall OEE percentage |

---

## 🤝 Contributing

This is a personal project for manufacturing KPI analysis. Feel free to fork and adapt for your own use cases.

---

## 📄 License

This project is open source and available for educational and commercial use.

---

## 🔧 Troubleshooting

### Arduino Not Connecting
- Check USB cable connection
- Verify port in `config.yaml` matches your system
- Grant terminal permissions to access USB devices (macOS)
- The script will auto-scan for USB devices if initial connection fails

### Dashboard Not Showing Data
- Ensure `oee_monitor.py` is running and creating CSV files
- Check that `oee_logs/` directory exists and contains CSV files
- Verify file paths in dashboard match your system

### Dependencies Issues
```bash
# Clean install
rm -rf .venv uv.lock
uv sync
```



