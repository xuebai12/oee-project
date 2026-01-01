import streamlit as st
import pandas as pd
import sqlite3
import time
import os
import yaml
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta

# --- 1. Load Configuration ---
def load_config():
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        return {
            'production': {'target_steps': 30, 'ideal_cycle_time': 20.0},
            'database': {'path': 'oee_data.db'}
        }
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

CONFIG = load_config()
TARGET_STEPS = CONFIG['production']['target_steps']
IDEAL_CYCLE_TIME = CONFIG['production']['ideal_cycle_time']
DB_PATH = CONFIG['database']['path']

# --- 2. Page Config ---
st.set_page_config(
    page_title="Factory Sight - Real-Time Monitor",
    page_icon="🏭",
    layout="wide",
)

# Custom CSS
st.markdown("""
    <style>
    .status-card { padding: 20px; border-radius: 10px; text-align: center; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .status-title { font-size: 24px; opacity: 0.9; margin-bottom: 10px; }
    .status-value { font-size: 60px; font-weight: 800; letter-spacing: 2px; }
    .status-green { background: linear-gradient(135deg, #2ecc71, #27ae60); }
    .status-yellow { background: linear-gradient(135deg, #f1c40f, #f39c12); color: #2c3e50; }
    .status-red { background: linear-gradient(135deg, #e74c3c, #c0392b); }
    .status-gray { background: linear-gradient(135deg, #95a5a6, #7f8c8d); }
    .final-report-card { background-color: #f0fdf4; border: 2px solid #22c55e; padding: 30px; border-radius: 15px; text-align: center; margin-top: 20px; margin-bottom: 40px; }
    
    .report-item { margin: 10px; text-align: center; }
    .report-label { font-size: 14px; color: #555; font-weight: bold; text-transform: uppercase; margin-top: 5px; }
    .report-value { font-size: 28px; font-weight: 800; color: #1f2937; }
    .report-value-main { font-size: 60px; font-weight: 900; color: #15803d; line-height: 1; }
    </style>
    """, unsafe_allow_html=True)

# --- Session State ---
if 'production_finished' not in st.session_state: st.session_state['production_finished'] = False
if 'report_generated' not in st.session_state: st.session_state['report_generated'] = False
if 'final_results' not in st.session_state: st.session_state['final_results'] = {}

# --- 3. Helper Functions ---

def get_data_from_db():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        # 映射数据库列名到 UI 所需的列名
        query = "SELECT * FROM oee_logs ORDER BY id ASC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        rename_map = {
            'prod_time': 'Production_Time(s)',
            'setup_time': 'Setup_Time(s)',
            'down_time': 'Downtime_Time(s)',
            'oee': 'OEE(%)',
            'availability': 'Availability(%)',
            'performance': 'Performance(%)',
            'quality': 'Quality(%)',
            'timestamp': 'Timestamp',
            'state': 'State',
            'total_count': 'Total_Count',
            'defect_count': 'Defect_Count'
        }
        df.rename(columns=rename_map, inplace=True)
        return df
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()

def calculate_eta(df):
    if df.empty: return "Calculating..."
    last_row = df.iloc[-1]
    total_count = last_row.get('Total_Count', 0)
    prod_time = last_row.get('Production_Time(s)', 0)
    
    remaining_steps = max(0, TARGET_STEPS - total_count)
    if total_count > 0:
        avg_cycle_time = prod_time / total_count
    else:
        avg_cycle_time = IDEAL_CYCLE_TIME
    
    seconds_left = remaining_steps * avg_cycle_time
    return (datetime.now() + timedelta(seconds=seconds_left)).strftime("%H:%M:%S")

def render_dashboard_ui(df, is_frozen=False):
    if df.empty: 
        st.warning("Waiting for data...")
        return

    last_row = df.iloc[-1]
    current_state = last_row.get('State', 'STOPPED')
    
    st.markdown(f"### 📡 Process Data Visualization {'(LIVE)' if not is_frozen else '(FROZEN)'}")

    if not is_frozen:
        if current_state == "GREEN":
            st.markdown(f"""<div class="status-card status-green"><div class="status-title">STATUS</div><div class="status-value">⚡ PRODUCTION</div><div>Running Smoothly</div></div>""", unsafe_allow_html=True)
        elif current_state == "YELLOW":
            st.markdown(f"""<div class="status-card status-yellow"><div class="status-title">STATUS</div><div class="status-value">⚠️ SETUP</div><div>Preparation in Progress</div></div>""", unsafe_allow_html=True)
        elif current_state == "STOPPED":
            st.markdown(f"""<div class="status-card status-gray"><div class="status-title">STATUS</div><div class="status-value">⏸️ STOPPED</div><div>System Ready</div></div>""", unsafe_allow_html=True)
        else: 
            st.markdown(f"""<div class="status-card status-red"><div class="status-title">STATUS</div><div class="status-value">🛑 DOWNTIME</div><div>Production Stopped</div></div>""", unsafe_allow_html=True)

    # KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    oee_val = last_row.get('OEE(%)', 0)
    avail_val = last_row.get('Availability(%)', 0)
    perf_val = last_row.get('Performance(%)', 0)
    qual_val = last_row.get('Quality(%)', 0)
    
    k1.metric("🎰 OEE Score", f"{oee_val}%", f"{oee_val-85:.1f}% Target")
    k2.metric("⏱️ Availability", f"{avail_val}%")
    k3.metric("📦 Output", f"{last_row.get('Total_Count', 0)} / {TARGET_STEPS}", f"ETA: {calculate_eta(df)}")
    k4.metric("🛡️ Quality", f"{qual_val}%", f"{last_row.get('Defect_Count', 0)} Defects", delta_color="inverse")

    st.divider()

    # Charts
    col_timeline, col_stats = st.columns([2, 1])
    with col_timeline:
        tab_trend, tab_state = st.tabs(["📈 Trend", "⏳ Timeline"])
        with tab_trend:
            chart_cols = ['Timestamp', 'OEE(%)', 'Availability(%)', 'Performance(%)', 'Quality(%)']
            valid_cols = [c for c in chart_cols if c in df.columns]
            chart_data = df[valid_cols].tail(100) if not is_frozen else df[valid_cols]
            if len(valid_cols) > 1:
                st.line_chart(chart_data.set_index('Timestamp'))
            
        with tab_state:
            chart_df = df.tail(100).copy() if not is_frozen else df.copy()
            color_map = {'GREEN': '#2ecc71', 'YELLOW': '#f1c40f', 'RED': '#e74c3c', 'STOPPED': '#95a5a6'}
            fig = px.scatter(chart_df, x='Timestamp', y='State', color='State', color_discrete_map=color_map, height=250)
            st.plotly_chart(fig, use_container_width=True, key=f"timeline_{uuid.uuid4()}")

    with col_stats:
        st.markdown("#### 📊 Loss Analysis")
        prod_t = last_row.get('Production_Time(s)', 0)
        setup_t = last_row.get('Setup_Time(s)', 0)
        down_t = last_row.get('Downtime_Time(s)', 0)
        
        fig_pie = go.Figure(data=[go.Pie(labels=['Production', 'Setup', 'Downtime'], values=[prod_t, setup_t, down_t], hole=.6, marker_colors=['#2ecc71', '#f1c40f', '#e74c3c'])])
        fig_pie.update_layout(height=250, margin=dict(t=0,b=0,l=0,r=0), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_{uuid.uuid4()}")

# --- 4. Sidebar ---
with st.sidebar:
    st.title("🏭 Factory Sight")
    st.caption("SQLite Real-Time Monitor")
    st.divider()
    
    if st.button("🗑️ Clear Database", help="Danger: This will delete all logs!"):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            st.success("Database cleared!")
            time.sleep(1)
            st.rerun()

    st.divider()
    st.markdown("### � Settings")
    st.write(f"**Target:** {TARGET_STEPS} Steps")
    st.write(f"**Ideal Takt:** {IDEAL_CYCLE_TIME}s")
    
    st.divider()
    if not st.session_state['production_finished']:
        if st.button("🛑 End Production Batch", type="primary", use_container_width=True):
            st.session_state['production_finished'] = True
            st.rerun()
    else:
        if st.button("🔄 Start New Batch", use_container_width=True):
            st.session_state['production_finished'] = False
            st.session_state['report_generated'] = False
            st.session_state['final_results'] = {}
            st.rerun()

# --- 5. Main Logic ---
placeholder = st.empty()

if st.session_state['production_finished']:
    with placeholder.container():
        if st.session_state['report_generated']:
            res = st.session_state['final_results']
            st.markdown(f"""
            <div class="final-report-card">
                <h2 style="color:#15803d; margin-bottom:0;">🎉 FINAL SHIFT REPORT</h2>
                <hr style="border-color:#86efac;">
                <div style="margin-top: 30px; margin-bottom: 30px;">
                    <div class="report-value-main">{res['oee']:.1f}%</div>
                    <div class="report-label" style="font-size: 18px;">🏆 FINAL OEE SCORE</div>
                </div>
                <div style="display:flex; justify-content:center; gap: 40px; flex-wrap: wrap;">
                    <div class="report-item"><div class="report-value">{res['avail']:.1f}%</div><div class="report-label">⏱️ Availability</div></div>
                    <div class="report-item"><div class="report-value">{res['perf']:.1f}%</div><div class="report-label">🚀 Performance</div></div>
                    <div class="report-item"><div class="report-value">{res['qual']:.1f}%</div><div class="report-label">🛡️ Quality</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("## 🛑 Batch Production Ended")
            df = get_data_from_db()
            if not df.empty:
                last_row = df.iloc[-1]
                last_avail = last_row.get('Availability(%)', 0)
                last_perf = last_row.get('Performance(%)', 0)
                
                with st.form("final_qc_form"):
                    defects_input = st.number_input("Enter Defects Count", 0, TARGET_STEPS, 0)
                    if st.form_submit_button("✅ Generate Final Report"):
                        good_count = TARGET_STEPS - defects_input
                        quality = (good_count / TARGET_STEPS) * 100
                        final_oee = (last_avail / 100) * (last_perf / 100) * (quality / 100) * 100
                        st.session_state['final_results'] = {'oee': final_oee, 'qual': quality, 'avail': last_avail, 'perf': last_perf}
                        st.session_state['report_generated'] = True
                        st.balloons()
                        st.rerun()
        
        df = get_data_from_db()
        render_dashboard_ui(df, is_frozen=True)
else:
    # 实时更新
    while True:
        df = get_data_from_db()
        with placeholder.container():
            render_dashboard_ui(df, is_frozen=False)
        time.sleep(2)