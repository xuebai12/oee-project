
# OEE Project (Overall Equipment Effectiveness)

This project is a Python-based tool designed to calculate and analyze OEE for our production lines. 

## 🛠 Prerequisites

Before you start, make sure you have the following installed on your Mac:
* **Python** (version 3.10 or higher)
### Installation
We use `uv` to manage our Python environment and packages. If you don't have it, install it via terminal:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Running the Dashboard
To run the dashboard locally:
```bash
uv run streamlit run src/oee/dashboardv1.py
```
This will automatically install dependencies and launch the app in your browser.
