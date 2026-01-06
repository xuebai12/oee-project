import streamlit as st
import pandas as pd
import time
import os
import glob
import yaml
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. Load Configuration & Path (加载配置与路径) ---
def load_config():
    """
    Load project configuration and determine the log directory path.
    获取项目配置并确定日志文件夹路径。
    """
    # 🌟 Get home directory (e.g., /Users/baixue)
    home_dir = os.path.expanduser("~")
    
    # 📂 Construct the path to the OEE logs directory
    # 拼接完整的日志目录路径: /Users/baixue/oee-project/oee_logs
    log_dir = os.path.join(home_dir, "oee-project", "oee_logs")
    
    # Default settings
    config = {
        'production': {
            'target_steps': 30,
            'ideal_cycle_time': 20.0
        },
        'data_path': log_dir
    }

    # Load from config.yaml if it exists
    # We assume the app is run from the project root
    config_path = "config.yaml"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Update production settings
                    if 'production' in user_config:
                        config['production'].update(user_config['production'])
                    
                    # Security: Validate data_path if provided
                    if 'data_path' in user_config:
                        proposed_path = user_config['data_path']
                        # Simple validation: ensure it's absolute or relative to project
                        # In a real scenario, we might want to restrict to specific subdirs
                        if os.path.isabs(proposed_path) or not proposed_path.startswith(".."):
                             config['data_path'] = proposed_path
                        else:
                            st.error(f"⚠️ Security Warning: Invalid data_path '{proposed_path}' ignored.")
        except Exception as e:
            print(f"Error loading config.yaml: {e}")

    return config


# Initialize global constants from config
CONFIG = load_config()
TARGET_STEPS = CONFIG['production']['target_steps']
IDEAL_CYCLE_TIME = CONFIG['production']['ideal_cycle_time']
LOG_DIR = CONFIG['data_path']

# --- 2. Page Config ---
st.set_page_config(
    page_title="Factory Sight - Log Monitor",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for final report
if 'session_ended' not in st.session_state:
    st.session_state.session_ended = False
if 'final_defect_count' not in st.session_state:
    st.session_state.final_defect_count = 0
if 'show_defect_input' not in st.session_state:
    st.session_state.show_defect_input = False

# Initialize session state for history viewer
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'live'  # 'live' or 'history'
if 'selected_session' not in st.session_state:
    st.session_state.selected_session = None

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
    </style>
    """, unsafe_allow_html=True)

# --- 3. Helper Functions (Modified for CSV) ---

def get_session_list():
    """
    Get list of all CSV session files with metadata.
    获取所有 CSV session 文件及其元数据。
    """
    if not os.path.exists(LOG_DIR):
        return []
    
    all_files = glob.glob(os.path.join(LOG_DIR, "*.csv"))
    sessions = []
    
    for filepath in all_files:
        try:
            filename = os.path.basename(filepath)
            # Extract timestamp from filename (e.g., OEE_Log_20251231_152801.csv)
            if filename.startswith("OEE_Log_"):
                timestamp_str = filename.replace("OEE_Log_", "").replace(".csv", "")
                # Parse timestamp
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                # Read last row to get final OEE
                df = pd.read_csv(filepath)
                if not df.empty:
                    last_row = df.iloc[-1]
                    final_oee = last_row.get('OEE', 0)
                    
                    sessions.append({
                        'filepath': filepath,
                        'filename': filename,
                        'timestamp': dt,
                        'display_name': dt.strftime("%Y-%m-%d %H:%M:%S"),
                        'final_oee': final_oee
                    })
        except Exception:
            pass
    
    # Sort by timestamp, newest first
    sessions.sort(key=lambda x: x['timestamp'], reverse=True)
    return sessions

def load_session_data(filepath):
    """
    Load data from a specific session CSV file.
    从特定的 session CSV 文件加载数据。
    """
    try:
        df = pd.read_csv(filepath)
        df.fillna(0, inplace=True)
        
        # Parse timestamp
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            df = df.sort_values(by='Timestamp')
        
        # Apply column mapping
        rename_map = {
            'Prod_Time': 'Production_Time(s)',
            'Setup_Time': 'Setup_Time(s)',
            'Down_Time': 'Downtime_Time(s)',
            'A': 'Availability(%)',
            'P': 'Performance(%)',
            'Q': 'Quality(%)',
            'OEE': 'OEE(%)',
            'Total_Count': 'Total_Count',
            'Defects': 'Defect_Count'
        }
        df.rename(columns=rename_map, inplace=True)
        
        return df
    except Exception as e:
        return pd.DataFrame()

def get_data_from_csvs():

    # Check if the log directory exists
    if not os.path.exists(LOG_DIR):
        return pd.DataFrame(), f"❌ Path not found (路径未找到): {LOG_DIR}"

    # Find all CSV files in the logs directory
    # 路径类似: /Users/baixue/oee-project/oee_logs/*.csv
    all_files = glob.glob(os.path.join(LOG_DIR, "*.csv"))
    
    if not all_files:
        return pd.DataFrame(), f"⚠️ No CSV files found (目录为空): {LOG_DIR}"

    try:
        df_list = []
        for filename in all_files:
            try:
                # 🛡️ Prevent errors from reading empty or locked files
                if os.path.getsize(filename) > 0:
                    df_list.append(pd.read_csv(filename))
            except Exception:
                pass # Skip corrupted or unreadable files
        
        if not df_list:
            return pd.DataFrame(), "⚠️ All CSV files are empty or unreadable."

        # Combine all individual CSVs into one table
        full_df = pd.concat(df_list, ignore_index=True)
        
        # 🧹 Data Cleaning: Handle NaN (empty values)
        # If there are calculation errors resulting in NaN, replace with 0
        full_df.fillna(0, inplace=True)
        
        # Parse timestamp string into datetime objects for sorting/plotting
        if 'Timestamp' in full_df.columns:
            # Explicitly parse with format to avoid warnings and errors
            # The format in oee_monitor.py is typically %Y-%m-%d %H:%M:%S
            # We use errors='coerce' to handle any malformed lines gracefully
            full_df['Timestamp'] = pd.to_datetime(full_df['Timestamp'], format='mixed', errors='coerce')
            full_df = full_df.sort_values(by='Timestamp')
        
        # --- 🗺️ Column Mapping (字段映射) ---
        # Map raw CSV headers (from oee_monitor.py) to UI-friendly display names
        # 将原始 CSV 列名（来自 monitor）映射到 UI 友好的显示名称
        rename_map = {
            'Prod_Time': 'Production_Time(s)',
            'Setup_Time': 'Setup_Time(s)',
            'Down_Time': 'Downtime_Time(s)',
            'A': 'Availability(%)',
            'P': 'Performance(%)',
            'Q': 'Quality(%)',
            'OEE': 'OEE(%)',
            'Total_Count': 'Total_Count',
            'Defects': 'Defect_Count'
        }
        
        raw_columns = list(full_df.columns)
        full_df.rename(columns=rename_map, inplace=True)
        
        return full_df, f"✅ Loaded {len(all_files)} files. (Raw cols: {raw_columns})"
        
    except Exception as e:
        return pd.DataFrame(), f"❌ Error reading logs: {str(e)}"

def calculate_eta(df):
    """
    Estimate when the target production count will be reached.
    """
    if df.empty: return "Calculating..."
    last_row = df.iloc[-1]
    total_count = last_row.get('Total_Count', 0)
    
    remaining_steps = max(0, TARGET_STEPS - total_count)
    if remaining_steps == 0: return "Done"
    
    # Simple calculation based on ideal cycle time
    seconds_left = remaining_steps * IDEAL_CYCLE_TIME
    return (datetime.now() + timedelta(seconds=seconds_left)).strftime("%H:%M:%S")

def render_dashboard_ui(df, msg, show_debug):
    """
    Main function to render the Streamlit user interface components.
    渲染 Streamlit 用户界面的主体函数。n    """
    # --- Debug Info Section (调试信息) ---
    if show_debug:
        st.warning("🛠️ DEBUG MODE ACTIVE")
        st.code(f"Target Directory: {LOG_DIR}")
        st.code(f"System Message: {msg}")
        if not df.empty:
            st.write("First 3 rows of data (前三行数据):", df.head(3))
        st.divider()

    # If no data is available yet
    if df.empty: 
        if not show_debug:
            st.info(f"⏳ Waiting for CSV logs... (Turn on 'Debug Info' in sidebar to see path)")
        return

    # Get the most recent state and metrics
    last_row = df.iloc[-1]
    current_state = last_row.get('State', 'STOPPED')
    
    # --- Final Report Mode ---
    if st.session_state.session_ended:
        st.markdown("### 📊 Final Production Report")
        
        # Big success banner
        st.success("✅ Production Session Completed!")
        
        # Final metrics in large cards
        col1, col2, col3, col4 = st.columns(4)
        
        oee_val = last_row.get('OEE(%)', 0)
        avail_val = last_row.get('Availability(%)', 0)
        perf_val = last_row.get('Performance(%)', 0)
        qual_val = last_row.get('Quality(%)', 0)
        total_count = last_row.get('Total_Count', 0)
        final_defects = st.session_state.final_defect_count
        
        with col1:
            st.metric("🎰 Final OEE Score", f"{oee_val:.1f}%", 
                     delta=f"{oee_val-85:.1f}% vs Target",
                     delta_color="normal" if oee_val >= 85 else "inverse")
        with col2:
            st.metric("⏱️ Availability", f"{avail_val:.1f}%")
        with col3:
            st.metric("⚡ Performance", f"{perf_val:.1f}%")
        with col4:
            st.metric("🛡️ Quality", f"{qual_val:.1f}%")
        
        st.divider()
        
        # Production summary
        sum1, sum2, sum3 = st.columns(3)
        with sum1:
            st.markdown("#### 📦 Production Output")
            st.markdown(f"**Total Units:** {TARGET_STEPS}")
            st.markdown(f"**Good Units:** {TARGET_STEPS - final_defects}")
            st.markdown(f"**Defective Units:** {final_defects}")
        
        with sum2:
            st.markdown("#### ⏱️ Time Breakdown")
            prod_t = last_row.get('Production_Time(s)', 0)
            setup_t = last_row.get('Setup_Time(s)', 0)
            down_t = last_row.get('Downtime_Time(s)', 0)
            total_t = prod_t + setup_t + down_t
            st.markdown(f"**Production Time:** {prod_t:.1f}s ({prod_t/total_t*100:.1f}%)")
            st.markdown(f"**Setup Time:** {setup_t:.1f}s ({setup_t/total_t*100:.1f}%)")
            st.markdown(f"**Downtime:** {down_t:.1f}s ({down_t/total_t*100:.1f}%)")
            
            # Add pie chart for time distribution
            if total_t > 0:
                fig_time = go.Figure(data=[go.Pie(
                    labels=['Production', 'Setup', 'Downtime'],
                    values=[prod_t, setup_t, down_t],
                    hole=.4,
                    marker_colors=['#2ecc71', '#f1c40f', '#e74c3c']
                )])
                fig_time.update_layout(
                    height=200,
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=11)
                )
                st.plotly_chart(fig_time, use_container_width=True, key=f"time_pie_{uuid.uuid4()}")
        
        with sum3:
            st.markdown("#### 🎯 Performance vs Target")
            if oee_val >= 85:
                st.markdown("✅ **Target Achieved!**")
            else:
                st.markdown("⚠️ **Below Target**")
            st.markdown(f"**Gap:** {85-oee_val:.1f}%")
        
        st.divider()
        
        # State Change Log Table
        st.markdown("#### 📋 State Change Log")
        if 'State' in df.columns and 'Timestamp' in df.columns:
            # Filter to only show rows where state changed
            state_changes = []
            prev_state = None
            for idx, row in df.iterrows():
                current_state = row.get('State')
                if current_state != prev_state:
                    state_changes.append({
                        'Timestamp': row.get('Timestamp'),
                        'State': current_state,
                        'OEE(%)': row.get('OEE(%)', 0)
                    })
                    prev_state = current_state
            
            if state_changes:
                state_df = pd.DataFrame(state_changes)
                # Format the display
                state_df['Timestamp'] = pd.to_datetime(state_df['Timestamp']).dt.strftime('%H:%M:%S')
                state_df['OEE(%)'] = state_df['OEE(%)'].apply(lambda x: f"{x:.1f}%")
                
                # Add emoji indicators for states
                state_emoji = {
                    'GREEN': '⚡ PRODUCTION',
                    'YELLOW': '⚠️ SETUP',
                    'RED': '🛑 DOWNTIME',
                    'STOPPED': '⏸️ STOPPED'
                }
                state_df['State'] = state_df['State'].map(state_emoji)
                
                # Display as table
                st.dataframe(
                    state_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Timestamp': st.column_config.TextColumn('Time', width="small"),
                        'State': st.column_config.TextColumn('Status', width="medium"),
                        'OEE(%)': st.column_config.TextColumn('OEE', width="small")
                    }
                )
                st.caption(f"📊 Total state changes: {len(state_changes)}")
        
        st.divider()
        
        # Historical chart
        st.markdown("#### 📈 Session Trend")
        chart_cols = ['Timestamp', 'OEE(%)', 'Availability(%)', 'Performance(%)']
        valid_cols = [c for c in chart_cols if c in df.columns]
        if len(valid_cols) > 1:
            chart_data = df[valid_cols]
            st.line_chart(chart_data.set_index('Timestamp'))
        
        return  # Exit early, don't show live dashboard
    
    # --- Live Dashboard Mode (实时监控模式) ---
    st.markdown(f"### 📡 Process Data Visualization (Source: CSV Files)")

    # Status Card (顶部状态卡片)
    # Displays the current machine state with dynamic colors
    if current_state == "GREEN":
        st.markdown(f"""<div class="status-card status-green"><div class="status-title">STATUS</div><div class="status-value">⚡ PRODUCTION</div><div>Running Smoothly</div></div>""", unsafe_allow_html=True)
    elif current_state == "YELLOW":
        st.markdown(f"""<div class="status-card status-yellow"><div class="status-title">STATUS</div><div class="status-value">⚠️SETUP</div><div>Preparation</div></div>""", unsafe_allow_html=True)
    elif current_state == "STOPPED":
        st.markdown(f"""<div class="status-card status-gray"><div class="status-title">STATUS</div><div class="status-value">⏸️ STOPPED</div><div>System Ready</div></div>""", unsafe_allow_html=True)
    else: 
        st.markdown(f"""<div class="status-card status-red"><div class="status-title">STATUS</div><div class="status-value">🛑 DOWNTIME</div><div>Stopped</div></div>""", unsafe_allow_html=True)

    # KPI Cards (关键绩效指标)
    k1, k2, k3, k4 = st.columns(4)
    oee_val = last_row.get('OEE(%)', 0)
    avail_val = last_row.get('Availability(%)', 0)
    
    # 🎰 OEE Score = Availability * Performance * Quality
    k1.metric("🎰 OEE Score", f"{oee_val:.1f}%", f"{oee_val-85:.1f}% Target")
    # ⏱️ Availability = Actual Production Time / Total Planned Time
    k2.metric("⏱️ Availability", f"{avail_val:.1f}%")
    # 📦 Output = Current Count / Target Count
    k3.metric("📦 Output", f"{last_row.get('Total_Count', 0)} / {TARGET_STEPS}", f"ETA: {calculate_eta(df)}")
    # 🛡️ Quality = Good Units / Total Units
    k4.metric("🛡️ Quality", f"{last_row.get('Quality(%)', 0):.1f}%", f"{last_row.get('Defect_Count', 0)} Defects", delta_color="inverse")

    st.divider()

    # Charts (图表区域)
    col_timeline, col_stats = st.columns([2, 1])
    with col_timeline:
        tab_trend, tab_state = st.tabs(["📈 Trend", "⏳ Timeline"])
        with tab_trend:
            # Main OEE metrics trend over time
            chart_cols = ['Timestamp', 'OEE(%)', 'Availability(%)', 'Performance(%)']
            valid_cols = [c for c in chart_cols if c in df.columns]
            if len(valid_cols) > 1:
                chart_data = df[valid_cols].tail(50) 
                st.line_chart(chart_data.set_index('Timestamp'))
            else:
                st.warning(f"Missing columns for chart. Found: {list(df.columns)}")
            
        with tab_state:
            # Scatter plot showing state transitions
            chart_df = df.tail(50).copy()
            if 'State' in chart_df.columns and 'Timestamp' in chart_df.columns:
                color_map = {'GREEN': '#2ecc71', 'YELLOW': '#f1c40f', 'RED': '#e74c3c', 'STOPPED': '#95a5a6'}
                fig = px.scatter(chart_df, x='Timestamp', y='State', color='State', color_discrete_map=color_map, height=250)
                # Beautify chart
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=10, b=10, l=10, r=10),
                    font=dict(size=11)
                )
                # Use a unique key for Plotly objects in dynamic loops
                st.plotly_chart(fig, use_container_width=True, key=f"timeline_{uuid.uuid4()}")

    with col_stats:
        st.markdown("#### 📊 Loss Analysis")
        # Pie chart showing the distribution of time
        prod_t = last_row.get('Production_Time(s)', 0)
        setup_t = last_row.get('Setup_Time(s)', 0)
        down_t = last_row.get('Downtime_Time(s)', 0)
        
        # OEE visualization breakdown
        fig_pie = go.Figure(data=[go.Pie(labels=['Production', 'Setup', 'Downtime'], values=[prod_t, setup_t, down_t], hole=.6, marker_colors=['#2ecc71', '#f1c40f', '#e74c3c'])])
        fig_pie.update_layout(
            height=250,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_{uuid.uuid4()}")

# --- 4. Sidebar (侧边栏控制) ---
with st.sidebar:
    st.title("🏭 Factory Sight")
    st.caption("CSV Log Monitor")
    
    # 调试开关
    show_debug = st.checkbox("🐞 Show Debug Info", value=False)
    
    st.divider()
    
    # --- End Session Feature (结束会话功能) ---
    if not st.session_state.session_ended:
        st.markdown("### 🎬 Session Control")
        
        if st.button("🏁 End Session", type="primary", use_container_width=True):
            st.session_state.show_defect_input = True
        
        # Defect input dialog
        if st.session_state.show_defect_input:
            with st.form("defect_form"):
                st.markdown("#### Enter Final Defect Count")
                defect_input = st.number_input(
                    "Number of defective units :",
                    min_value=0,
                    max_value=1000,
                    value=0,
                    step=1
                )
                
                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submitted = st.form_submit_button("✅ Confirm", use_container_width=True)
                with col_cancel:
                    cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
                
                if submitted:
                    st.session_state.final_defect_count = defect_input
                    st.session_state.session_ended = True
                    st.session_state.show_defect_input = False
                    st.rerun()
                
                if cancelled:
                    st.session_state.show_defect_input = False
                    st.rerun()
        
        st.divider()
    else:
        st.success("✅ Session Ended")
        if st.button("🔄 Start New Session", use_container_width=True):
            st.session_state.session_ended = False
            st.session_state.final_defect_count = 0
            st.session_state.show_defect_input = False
            st.rerun()
        st.divider()
    
    if st.button("🔄 Refresh Data"):
        st.rerun()
    
    st.divider()
    
    # --- Historical Session Viewer (历史记录查看) ---
    st.markdown("### � Historical Sessions")
    
    sessions = get_session_list()
    
    if sessions:
        # View mode toggle
        if st.session_state.view_mode == 'live':
            st.info(f"📊 {len(sessions)} session(s) available")
            
            # Session selector
            session_options = [f"{s['filename']} (OEE: {s['final_oee']:.1f}%)" for s in sessions]
            selected_idx = st.selectbox(
                "Select a session to view:",
                range(len(sessions)),
                format_func=lambda i: session_options[i],
                key="session_selector"
            )
            
            if st.button("👁️ View Session Report", use_container_width=True):
                st.session_state.selected_session = sessions[selected_idx]['filepath']
                st.session_state.view_mode = 'history'
                st.rerun()
        else:
            # Currently viewing history
            st.success("📖 Viewing Historical Session")
            if st.button("⬅️ Back to Live", use_container_width=True):
                st.session_state.view_mode = 'live'
                st.session_state.selected_session = None
                st.rerun()
    else:
        st.warning("No historical sessions found")

# --- 5. Main Loop (主程序运行) ---
placeholder = st.empty()

# 🔄 Step 1: Fetch data based on view mode
if st.session_state.view_mode == 'history' and st.session_state.selected_session:
    # Load historical session data
    df = load_session_data(st.session_state.selected_session)
    msg = f"✅ Loaded historical session: {os.path.basename(st.session_state.selected_session)}"
else:
    # Load live data (merge all CSVs)
    df, msg = get_data_from_csvs()

# 🎨 Step 2: Render the dashboard layout inside the placeholder
with placeholder.container():
    # In history mode, show as a final report
    if st.session_state.view_mode == 'history':
        if not df.empty:
            last_row = df.iloc[-1]
            
            st.markdown("### 📊 Historical Session Report")
            st.info(msg)
            
            # Final metrics in large cards
            col1, col2, col3, col4 = st.columns(4)
            
            oee_val = last_row.get('OEE(%)', 0)
            avail_val = last_row.get('Availability(%)', 0)
            perf_val = last_row.get('Performance(%)', 0)
            qual_val = last_row.get('Quality(%)', 0)
            total_count = last_row.get('Total_Count', 0)
            defect_count = last_row.get('Defect_Count', 0)
            
            with col1:
                st.metric("🎰 Final OEE Score", f"{oee_val:.1f}%", 
                         delta=f"{oee_val-85:.1f}% vs Target",
                         delta_color="normal" if oee_val >= 85 else "inverse")
            with col2:
                st.metric("⏱️ Availability", f"{avail_val:.1f}%")
            with col3:
                st.metric("⚡ Performance", f"{perf_val:.1f}%")
            with col4:
                st.metric("🛡️ Quality", f"{qual_val:.1f}%")
            
            st.divider()
            
            # Production summary
            sum1, sum2, sum3 = st.columns(3)
            with sum1:
                st.markdown("#### 📦 Production Output")
                st.markdown(f"**Total Units:** {TARGET_STEPS}")
                st.markdown(f"**Good Units:** {TARGET_STEPS - defect_count}")
                st.markdown(f"**Defective Units:** {defect_count}")
            
            with sum2:
                st.markdown("#### ⏱️ Time Breakdown")
                prod_t = last_row.get('Production_Time(s)', 0)
                setup_t = last_row.get('Setup_Time(s)', 0)
                down_t = last_row.get('Downtime_Time(s)', 0)
                total_t = prod_t + setup_t + down_t
                if total_t > 0:
                    st.markdown(f"**Production Time:** {prod_t:.1f}s ({prod_t/total_t*100:.1f}%)")
                    st.markdown(f"**Setup Time:** {setup_t:.1f}s ({setup_t/total_t*100:.1f}%)")
                    st.markdown(f"**Downtime:** {down_t:.1f}s ({down_t/total_t*100:.1f}%)")
                    
                    # Add pie chart for time distribution
                    fig_time = go.Figure(data=[go.Pie(
                        labels=['Production', 'Setup', 'Downtime'],
                        values=[prod_t, setup_t, down_t],
                        hole=.4,
                        marker_colors=['#2ecc71', '#f1c40f', '#e74c3c']
                    )])
                    fig_time.update_layout(
                        height=200,
                        margin=dict(t=10, b=10, l=10, r=10),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(size=11)
                    )
                    st.plotly_chart(fig_time, use_container_width=True, key=f"time_pie_hist_{uuid.uuid4()}")
            with sum3:
                st.markdown("#### 🎯 Performance vs Target")
                if oee_val >= 85:
                    st.markdown("✅ **Target Achieved!**")
                else:
                    st.markdown("⚠️ **Below Target**")
                st.markdown(f"**Gap:** {85-oee_val:.1f}%")
            
            st.divider()
            
            # State Change Log Table
            st.markdown("#### 📋 State Change Log")
            if 'State' in df.columns and 'Timestamp' in df.columns:
                # Filter to only show rows where state changed
                state_changes = []
                prev_state = None
                for idx, row in df.iterrows():
                    current_state = row.get('State')
                    if current_state != prev_state:
                        state_changes.append({
                            'Timestamp': row.get('Timestamp'),
                            'State': current_state,
                            'OEE(%)': row.get('OEE(%)', 0)
                        })
                        prev_state = current_state
                
                if state_changes:
                    state_df = pd.DataFrame(state_changes)
                    # Format the display
                    state_df['Timestamp'] = pd.to_datetime(state_df['Timestamp']).dt.strftime('%H:%M:%S')
                    state_df['OEE(%)'] = state_df['OEE(%)'].apply(lambda x: f"{x:.1f}%")
                    
                    # Add emoji indicators for states
                    state_emoji = {
                        'GREEN': '⚡ PRODUCTION',
                        'YELLOW': '⚠️ SETUP',
                        'RED': '🛑 DOWNTIME',
                        'STOPPED': '⏸️ STOPPED'
                    }
                    state_df['State'] = state_df['State'].map(state_emoji)
                    
                    # Display as table
                    st.dataframe(
                        state_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Timestamp': st.column_config.TextColumn('Time', width="small"),
                            'State': st.column_config.TextColumn('Status', width="medium"),
                            'OEE(%)': st.column_config.TextColumn('OEE', width="small")
                        }
                    )
                    st.caption(f"📊 Total state changes: {len(state_changes)}")
            
            st.divider()
            
            # Historical chart
            st.markdown("#### 📈 Session Trend")
            chart_cols = ['Timestamp', 'OEE(%)', 'Availability(%)', 'Performance(%)']
            valid_cols = [c for c in chart_cols if c in df.columns]
            if len(valid_cols) > 1:
                chart_data = df[valid_cols]
                st.line_chart(chart_data.set_index('Timestamp'))
        else:
            st.error("Failed to load historical session data")
    else:
        # Live mode - use existing render function
        render_dashboard_ui(df, msg, show_debug)

# ⏱️ Step 3: Auto-refresh mechanism (smoother than st.rerun)
# Only auto-refresh if in live mode and session is still active
if st.session_state.view_mode == 'live' and not st.session_state.session_ended:
    # Refresh every 2000ms (2 seconds) without the flashing
    st_autorefresh(interval=2000, key="data_refresh")