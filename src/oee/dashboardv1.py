import streamlit as st
import pandas as pd
import time
import os
import glob
import plotly.express as px
import plotly.graph_objects as go
import random
import uuid
from datetime import datetime, timedelta

# --- 1. Page Config ---
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
if 'final_defects' not in st.session_state: st.session_state['final_defects'] = 0
if 'final_results' not in st.session_state: st.session_state['final_results'] = {}
if 'report_generated' not in st.session_state: st.session_state['report_generated'] = False

# --- 2. Helper Functions ---

def get_latest_csv():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    log_dir = os.path.join(project_root, "oee_logs")
    search_pattern = os.path.join(log_dir, 'OEE_Log_*.csv')
    list_of_files = glob.glob(search_pattern) 
    if not list_of_files: return None
    return max(list_of_files, key=os.path.getctime)

def calculate_eta(df):
    if df.empty: return "Calculating..."
    last_row = df.iloc[-1]
    total_count = last_row.get('Total_Count', 0)
    prod_time = last_row.get('Production_Time(s)', 0)
    
    remaining_steps = max(0, TARGET_STEPS - total_count)
    if total_count > 0:
        avg_cycle_time = prod_time / total_count
    else:
        avg_cycle_time = 40.0
    
    seconds_left = remaining_steps * avg_cycle_time
    return (datetime.now() + timedelta(seconds=seconds_left)).strftime("%H:%M:%S")

def render_dashboard_ui(df, is_frozen=False):
    """核心 UI 渲染函数"""
    if df.empty: 
        st.warning("Data file is empty or invalid.")
        return

    last_row = df.iloc[-1]
    current_state = last_row.get('State', 'STOPPED')
    
    # 标题提示
    title_suffix = " (FULL HISTORY)" if is_frozen else " (LIVE STREAM)"
    st.markdown(f"### 📡 Process Data Visualization{title_suffix}")

    # 1. Status Banner (🔥 修改：定格模式下隐藏大横幅)
    if not is_frozen:
        if current_state == "GREEN":
            st.markdown(f"""<div class="status-card status-green"><div class="status-title">STATUS</div><div class="status-value">⚡ PRODUCTION</div><div>Running Smoothly</div></div>""", unsafe_allow_html=True)
        elif current_state == "YELLOW":
            st.markdown(f"""<div class="status-card status-yellow"><div class="status-title">STATUS</div><div class="status-value">⚠️ SETUP</div><div>Preparation in Progress</div></div>""", unsafe_allow_html=True)
        elif current_state == "STOPPED":
            st.markdown(f"""<div class="status-card status-gray"><div class="status-title">STATUS</div><div class="status-value">⏸️ STOPPED</div><div>System Ready</div></div>""", unsafe_allow_html=True)
        else: 
            st.markdown(f"""<div class="status-card status-red"><div class="status-title">STATUS</div><div class="status-value">🛑 DOWNTIME</div><div>Production Stopped</div></div>""", unsafe_allow_html=True)
    else:
        st.info("ℹ️ Displaying complete data history for this batch.")

    # 2. KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    oee_val = last_row.get('OEE(%)', 0)
    avail_val = last_row.get('Availability(%)', 0)
    perf_val = last_row.get('Performance(%)', 0)
    qual_val = last_row.get('Quality(%)', 0)
    
    k1.metric("🎰 OEE Score", f"{oee_val}%", f"{oee_val-85:.1f}% Target")
    k2.metric("⏱️ Availability", f"{avail_val}%", "Time")
    k3.metric("📦 Output", f"{last_row.get('Total_Count', 0)} / {TARGET_STEPS}", f"ETA: {calculate_eta(df)}")
    k4.metric("🛡️ Quality", f"{qual_val}%", f"{last_row.get('Defect_Count', 0)} Defects", delta_color="inverse")

    st.divider()

    # 3. Charts
    col_timeline, col_stats = st.columns([2, 1])
    with col_timeline:
        tab_trend, tab_state = st.tabs(["📈 Trend", "⏳ Timeline"])
        with tab_trend:
            chart_cols = ['Timestamp', 'OEE(%)', 'Availability(%)', 'Performance(%)', 'Quality(%)']
            valid_cols = [c for c in chart_cols if c in df.columns]
            
            # 🔥 修改：定格模式显示全部数据，实时模式只显示最近50条
            if is_frozen:
                chart_data = df[valid_cols]
            else:
                chart_data = df[valid_cols].tail(50)
                
            if len(valid_cols) > 1: st.line_chart(chart_data.set_index('Timestamp'))
            
        with tab_state:
            # 🔥 修改：定格模式显示全部数据
            if is_frozen:
                chart_df = df.copy()
            else:
                chart_df = df.tail(50).copy()
                
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

# --- 3. Sidebar ---
with st.sidebar:
    st.title("🏭 Factory Sight")
    st.caption("Real-Time Monitor")
    st.divider()
    
    st.markdown("### 📋 Settings")
    c1, c2 = st.columns(2)
    
    # 历史记录选择器
    log_dir = os.path.dirname(os.path.abspath(__file__)) # fallback
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        log_dir = os.path.join(project_root, "oee_logs")
    except: pass

    search_pattern = os.path.join(log_dir, 'OEE_Log_*.csv')
    log_files = glob.glob(search_pattern)
    
    selected_file_path = None
    is_live_mode = False
    
    if log_files:
        log_files.sort(key=os.path.getctime, reverse=True)
        file_map = {os.path.basename(f): f for f in log_files}
        selected_filename = st.selectbox("📂 Select Batch Log", list(file_map.keys()), index=0)
        selected_file_path = file_map[selected_filename]
        
        if selected_file_path == log_files[0]:
            is_live_mode = True
            st.success("🟢 LIVE MONITORING")
        else:
            is_live_mode = False
            st.warning("🟠 HISTORY VIEW")
    else:
        st.error("No logs found.")
    
    st.divider()
    
    TARGET_STEPS = 30
    IDEAL_TAKT_TIME = 20.0
    c1.metric("Target", f"{TARGET_STEPS}", "Steps")
    c2.metric("Takt", f"{int(IDEAL_TAKT_TIME)}s", "Ideal")
    
    st.divider()
    
    if is_live_mode:
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
    else:
        st.info("Controls disabled in History Mode.")

    st.divider()
    demo_mode = st.checkbox("🚀 Demo Mode", value=False)
    
# --- 4. Demo Data ---
def generate_fake_data(step, max_records=50):
    now = datetime.now()
    data = []
    for i in range(max_records):
        t = now - timedelta(seconds=(max_records-i)*2)
        state = random.choice(['GREEN', 'YELLOW', 'RED'])
        data.append({
            'Timestamp': t.strftime('%H:%M:%S'), 'State': state,
            'OEE(%)': 85.0, 'Availability(%)': 90.0, 'Performance(%)': 95.0, 'Quality(%)': 100.0,
            'Total_Count': 10, 'Defect_Count': 0,
            'Production_Time(s)': 100, 'Setup_Time(s)': 10, 'Downtime_Time(s)': 5
        })
    return pd.DataFrame(data)

def read_and_clean_data(csv_path, demo_mode, step_counter):
    if demo_mode: return generate_fake_data(step_counter)
    if not csv_path: return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        rename_map = {'Prod_Time':'Production_Time(s)', 'Setup_Time':'Setup_Time(s)', 'Down_Time':'Downtime_Time(s)', 'Total_Count':'Total_Count', 'Defects':'Defect_Count', 'OEE':'OEE(%)'}
        df.rename(columns=rename_map, inplace=True)
        df = df[df['Timestamp'] != 'FINAL_REPORT']
        return df
    except: return pd.DataFrame()

# --- 5. Main Logic ---
placeholder = st.empty()
step_counter = 1

# A. 历史模式 (History)
if not is_live_mode and not demo_mode:
    df = read_and_clean_data(selected_file_path, False, 0)
    with placeholder.container():
        st.markdown(f"### 📂 Viewing History: `{os.path.basename(selected_file_path)}`")
        render_dashboard_ui(df, is_frozen=True)

# B. 实时模式 (Live)
else:
    if st.session_state['production_finished'] and is_live_mode:
        with placeholder.container():
            if st.session_state['report_generated']:
                res = st.session_state['final_results']
                st.markdown(f"""
                <div class="final-report-card">
                    <h2 style="color:#15803d; margin-bottom:0;">🎉 FINAL SHIFT REPORT</h2>
                    <p style="color:#166534; margin-bottom: 20px;">Production Batch Complete</p>
                    <hr style="border-color:#86efac;">
                    <div style="margin-top: 30px; margin-bottom: 30px;">
                        <div class="report-value-main">{res['oee']:.1f}%</div>
                        <div class="report-label" style="font-size: 18px;">🏆 FINAL OEE SCORE</div>
                    </div>
                    <div style="display:flex; justify-content:center; gap: 40px; flex-wrap: wrap;">
                        <div class="report-item"><div class="report-value">{res['avail']:.1f}%</div><div class="report-label">⏱️ Availability</div></div>
                        <div class="report-item"><div class="report-value">{res['perf']:.1f}%</div><div class="report-label">🚀 Performance</div></div>
                        <div class="report-item"><div class="report-value">{res['qual']:.1f}%</div><div class="report-label">🛡️ Quality</div></div>
                        <div class="report-item"><div class="report-value" style="color:#ef4444;">{res['defects']}</div><div class="report-label">❌ Defects</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("## 🛑 Batch Production Ended")
                st.info("Please perform End-of-Line Quality Inspection.")
                
                df = read_and_clean_data(selected_file_path, demo_mode, 0)
                last_avail, last_perf = 0, 0
                if not df.empty:
                    last_row = df.iloc[-1]
                    last_avail = last_row.get('Availability(%)', 0)
                    last_perf = last_row.get('Performance(%)', 0)

                with st.form("final_qc_form"):
                    defects_input = st.number_input("Enter Defects Count", 0, 30, 0)
                    if st.form_submit_button("✅ Generate Final Report"):
                        good_count = TARGET_STEPS - defects_input
                        quality = (good_count / TARGET_STEPS) * 100
                        final_oee = (last_avail / 100) * (last_perf / 100) * (quality / 100) * 100
                        st.session_state['final_results'] = {'oee': final_oee, 'qual': quality, 'defects': defects_input, 'avail': last_avail, 'perf': last_perf}
                        st.session_state['report_generated'] = True
                        st.balloons()
                        st.rerun()

            # 🔥 定格时显示全部数据
            df = read_and_clean_data(selected_file_path, demo_mode, 0)
            st.markdown("---")
            render_dashboard_ui(df, is_frozen=True)

    else:
        while True:
            if demo_mode: step_counter += 1
            df = read_and_clean_data(selected_file_path, demo_mode, step_counter)
            with placeholder.container():
                render_dashboard_ui(df, is_frozen=False)
            time.sleep(1)