import streamlit as st
import time
import pandas as pd
from datetime import datetime
from module.modbus_client import PLCClient

# 1. Page Config - Forced Wide & No Scroll
st.set_page_config(page_title="VAJRA-NET | IoT Command", layout="wide")

# 2. HMI-Style CSS (Removes Sidebar, Adds Lab-White Aesthetic)
st.markdown("""
    <style>
    /* Global Reset */
    [data-testid="stSidebar"] { display: none; } /* Kill the side slider */
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden;
        background-color: #fcfcfc;
    }
    .main .block-container { padding: 1rem 3rem; max-width: 100%; }

    /* Top Control Bar */
    .control-panel {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 20px;
    }

    /* Live Big Value Card */
    .value-box {
        background: #ffffff;
        border-left: 10px solid #1a73e8;
        border-radius: 4px;
        padding: 40px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    .digital-font {
        font-family: 'Courier New', Courier, monospace;
        font-size: 7rem;
        font-weight: 900;
        color: #1a73e8;
        margin: 0;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Session State Logic
if "running" not in st.session_state: st.session_state.running = False
if "history" not in st.session_state: st.session_state.history = []

# --- HEADER & LIVE CLOCK ---
h_col1, h_col2 = st.columns([7, 3])
with h_col1:
    st.markdown("## VAJRA-NET <span style='color:#1a73e8; font-size:18px;'>CORE MONITOR</span>", unsafe_allow_html=True)
with h_col2:
    clock_placeholder = st.empty() # For the Live Time

# --- TOP CONTROL PANEL (Replaces Side Slider) ---
with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
    ip = c1.text_input("NODE IP", value="127.0.0.1")
    addr = c2.number_input("START ADDR", value=40001)
    reg_type = c3.selectbox("REG TYPE", ["HOLDING (4x)", "INPUT (3x)", "COIL (0x)"])
    data_type = c4.selectbox("FORMAT", ["FLOAT", "INT16", "UINT32"])
    
    # Toggle Button Logic
    if not st.session_state.running:
        if c5.button("▶ ENGAGE", use_container_width=True, type="primary"):
            st.session_state.running = True
            st.rerun()
    else:
        if c5.button("⏹ DISCONNECT", use_container_width=True):
            st.session_state.running = False
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- DASHBOARD AREA ---
col_left, col_right = st.columns([3, 2])

with col_left:
    st.caption("PRIMARY TELEMETRY")
    val_placeholder = st.empty()
    
    m1, m2 = st.columns(2)
    stat_integrity = m1.empty()
    stat_traffic = m2.empty()

with col_right:
    st.caption("SECURITY LOG (STATE CHANGES)")
    log_placeholder = st.empty()

# --- ENGINE ---
if st.session_state.running:
    # Set count based on format
    count = 2 if data_type in ["FLOAT", "UINT32"] else 1
    plc = PLCClient(ip, 502, 1)
    
    if plc.connect():
        while st.session_state.running:
            # 1. Update Live Clock
            clock_placeholder.markdown(f"<h3 style='text-align:right; margin:0;'>{datetime.now().strftime('%H:%M:%S')}</h3>", unsafe_allow_html=True)
            
            # 2. Fetch Modbus Data
            res, raw_hex = plc.read_registers(1, addr, count, reg_type)
            
            if res is not None:
                val = plc.decode(res, data_type, "MSR First (ABCD)")
                status, color = "LINK ACTIVE", "#1a73e8"
            else:
                val, status, color = "OFFLINE", "TIMEOUT", "#d93025"

            # 3. Update Value Card
            val_placeholder.markdown(f"""
                <div class="value-box" style="border-left-color: {color};">
                    <p style="color:gray; font-size:12px; font-weight:bold;">NODE: {ip}</p>
                    <h1 class="digital-font" style="color:{color};">{val}</h1>
                    <p style="color:{color}; font-weight:bold; letter-spacing:2px;">{status}</p>
                </div>
            """, unsafe_allow_html=True)

            stat_integrity.metric("INTEGRITY", "VERIFIED" if res else "FAILED")
            stat_traffic.metric("TRAFFIC", raw_hex if raw_hex else "0x00")

            # 4. History Log
            if res is not None and (not st.session_state.history or st.session_state.history[0]['Value'] != str(val)):
                st.session_state.history.insert(0, {"Time": datetime.now().strftime("%H:%M:%S"), "Value": str(val)})

            with log_placeholder.container(height=380):
                st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)

            time.sleep(0.5)
    else:
        st.error("Socket Error: Node Unreachable")
else:
    # Update clock even when not running
    clock_placeholder.markdown(f"<h3 style='text-align:right; margin:0;'>{datetime.now().strftime('%H:%M:%S')}</h3>", unsafe_allow_html=True)
    val_placeholder.info("System Ready. Click ENGAGE to start acquisition.")