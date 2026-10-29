import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime

# 1. ตั้งค่าหน้าเพจ (ต้องอยู่บรรทัดแรกสุด)
st.set_page_config(page_title="ระบบประเมินความเสี่ยง SLA ปข.3", layout="wide", initial_sidebar_state="expanded")

# 2. ใส่ CSS เพื่อทำธีม Glassmorphism และฟอนต์ Kanit
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif !important;
    }
    .stApp {
        background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
    }
    .glass-panel {
        background: rgba(255, 255, 255, 0.6);
        backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.8);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.05);
        margin-bottom: 20px;
    }
    .kpi-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.6) 100%);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# 3. โหลดข้อมูล
@st.cache_data(ttl=600) # Cache 10 นาที
def load_real_data():
    try:
        url = "https://docs.google.com/spreadsheets/d/11COh7oHLLJjsUOBTDmSRQqZADl1oVTZ3HnACcDnacdc/export?format=csv&gid=2062579029"
        df = pd.read_csv(url)
        df = df.rename(columns={
            df.columns[2]: 'Date', df.columns[3]: 'Region', 
            df.columns[5]: 'Branch', df.columns[6]: 'P', df.columns[7]: 'S'
        })
        df['P'] = pd.to_numeric(df['P'], errors='coerce').fillna(0)
        df['S'] = pd.to_numeric(df['S'], errors='coerce').fillna(0)
        df['Total'] = df['P'] + df['S']
        df = df[df['Branch'].notna() & (df['Branch'] != '')]
        
        df['Date'] = df['Date'].astype(str).str.strip()
        df['Date_parsed'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce'))
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], errors='coerce'))
        df = df[df['Date_parsed'].notna()]
        return df
    except Exception as e:
        return pd.DataFrame()

def get_risk_info(total):
    if total >= 100: return ("🔴 วิกฤต", "3.5 วัน", 1)
    elif total >= 30: return ("🟡 เฝ้าระวัง", "2.1 วัน", 2)
    else: return ("🟢 ปกติ", "1.2 วัน", 3)

df_main = load_real_data()

# 4. ส่วน Sidebar (แผงควบคุม)
with st.sidebar:
    st.markdown("<h3 style='text-align: center; color: #1E293B;'>🧊 แผงควบคุม</h3>", unsafe_allow_html=True)
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("**[ 🕒 วิเคราะห์ช่วงเวลา ]**")
    time_options = {"วันนี้": 1, "3 วัน": 3, "7 วัน": 7, "15 วัน": 15, "1 เดือน": 30, "3 เดือน": 90, "6 เดือน": 180, "1 ปี": 365}
    selected_time_label = st.radio("เลือกช่วงเวลา", list(time_options.keys()), index=2, label_visibility="collapsed")
    selected_time = time_options[selected_time_label]

    st.markdown("**[ 🏢 เลือก กลุ่ม ปจ. ]**")
    regions = ["ALL"] + sorted(df_main['Region'].dropna().unique().tolist())
    selected_region = st.selectbox("เลือก ปจ.", regions, label_visibility="collapsed")

    st.markdown("**[ 📍 ชื่อที่ทำการ ]**")
    if selected_region == "ALL":
        branches = ["ALL"] + sorted(df_main['Branch'].dropna().unique().tolist())
    else:
        branches = ["ALL"] + sorted(df_main[df_main['Region'] == selected_region]['Branch'].dropna().unique().tolist())
    selected_branch = st.selectbox("เลือกสาขา", branches, label_visibility="collapsed")

    st.markdown("**[ ⚠️ ระดับความเสี่ยง ]**")
    risk_1 = st.checkbox("🔴 วิกฤต", value=True)
    risk_2 = st.checkbox("🟡 เฝ้าระวัง", value=True)
    risk_3 = st.checkbox("🟢 ปกติ", value=True)
    selected_risks = []
    if risk_1: selected_risks.append(1)
    if risk_2: selected_risks.append(2)
    if risk_3: selected_risks.append(3)

# 5. ประมวลผลข้อมูล
if df_main.empty:
    st.error("ไม่พบข้อมูลจากระบบ กรุณาตรวจสอบการเชื่อมต่อ Google Sheets")
else:
    filtered_df = df_main.copy()
    max_date = filtered_df['Date_parsed'].max()
    
    if selected_time == 1:
        filtered_df = filtered_df[filtered_df['Date_parsed'] == max_date]
    else:
        cutoff_date = max_date - pd.Timedelta(days=selected_time)
        filtered_df = filtered_df[filtered_df['Date_parsed'] >= cutoff_date]

    if selected_region != "ALL":
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    if selected_branch != "ALL":
        filtered_df = filtered_df[filtered_df['Branch'] == selected_branch]
        
    latest_df = filtered_df.groupby(['Region', 'Branch'])[['P', 'S', 'Total']].sum().reset_index()
    
    risk_data = latest_df['Total'].apply(get_risk_info).tolist()
    latest_df['⚠️ SLA Risk'] = [r[0] for r in risk_data]
    latest_df['⏱️ วันค้าง'] = [r[1] for r in risk_data]
    latest_df['Risk Code'] = [r[2] for r in risk_data]
    
    latest_df = latest_df[latest_df['Risk Code'].isin(selected_risks)]
    latest_df = latest_df.sort_values(by='Total', ascending=False)
    
    top5_df = latest_df.head(5).copy().sort_values(by='Total', ascending=True)
    
    total_p = int(latest_df['P'].sum()) if not latest_df.empty else 0
    total_s = int(latest_df['S'].sum()) if not latest_df.empty else 0
    risk_count = len(latest_df[latest_df['Risk Code'] == 1])
    
    alert_branch = top5_df.iloc[-1]['Branch'] if not top5_df.empty else 'ไม่มี'

    # 6. วาด UI หลัก
    st.markdown("""
    <div class="glass-panel" style="border-top: 5px solid #4A90E2; display: flex; justify-content: space-between;">
        <div>
            <h3 style="font-weight: 800; color: #1E293B; margin-top: 0;">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA สลากกินแบ่งรัฐบาล</h3>
            <span style="background: rgba(255,255,255,0.7); padding: 5px 15px; border-radius: 20px; font-size: 14px; color: #475569;">
                🏢 พัฒนาระบบโดย สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if alert_branch != 'ไม่มี':
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FF416C, #FF4B2B); color: white; padding: 15px; border-radius: 15px; margin-bottom: 20px; font-weight: 600;">
            🚨 AI ALERT BANNER: [ 🔴 วิกฤต: ประเมินพบ 'สาขา{alert_branch}' คาดว่าจะจัดส่งสลากฯ ไม่ได้ตามมาตรฐาน SLA ที่ ปณท. กำหนด! ]
        </div>
        """, unsafe_allow_html=True)

    # KPIs
    kpi_title = f"ที่ทำการไปรษณีย์{selected_branch}" if selected_branch != "ALL" else (f"กลุ่ม ปจ.{selected_region}" if selected_region != "ALL" else "ภาพรวม ปข.3")
    st.markdown(f"<h4 style='color: #1E293B;'>📊 EXECUTIVE KPIs (ข้อมูลระดับ: {kpi_title})</h4>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div><p style="margin:0; color:#64748B; font-weight:700;">📦 ค้าง P (สถานะรอจ่าย)</p><h2 style="margin:0; color:#0F172A;">{total_p:,} ชิ้น</h2></div>
            <div style="width:50px; height:50px; background: linear-gradient(135deg, #FF416C, #FF4B2B); border-radius:12px; display:flex; justify-content:center; align-items:center; font-size:24px;">📦</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card">
            <div><p style="margin:0; color:#64748B; font-weight:700;">📝 ค้าง S/K/L (รับแล้ว/ส่งคืน)</p><h2 style="margin:0; color:#0F172A;">{total_s:,} ชิ้น</h2></div>
            <div style="width:50px; height:50px; background: linear-gradient(135deg, #F6D365, #FDA085); border-radius:12px; display:flex; justify-content:center; align-items:center; font-size:24px;">📝</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card">
            <div><p style="margin:0; color:#64748B; font-weight:700;">🚨 สาขาเสี่ยงตก SLA</p><h2 style="margin:0; color:#0F172A;">{risk_count} สาขา</h2></div>
            <div style="width:50px; height:50px; background: linear-gradient(135deg, #E74C3C, #C0392B); border-radius:12px; display:flex; justify-content:center; align-items:center; font-size:24px;">🚨</div>
        </div>""", unsafe_allow_html=True)

    # Charts
    st.markdown("<h4 style='color: #1E293B;'>🗺️ VISUAL ANALYTICS</h4>", unsafe_allow_html=True)
    
    cc1, cc2 = st.columns([6, 4])
    with cc1:
        st.markdown("<div class='glass-panel'><b>[ 📈 แนวโน้มการค้าง P vs S/K/L ]</b><br><span style='font-size:12px; color:#64748B;'>(เทียบเส้นเวลาใกล้วันที่ 5 และ 20 ของเดือน)</span>", unsafe_allow_html=True)
        daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
        fig_line = go.Figure()
        if not daily_trend.empty:
            fig_line.add_trace(go.Scatter(x=daily_trend['Date_parsed'], y=daily_trend['P'], mode='lines+markers', name='ค้าง P', line=dict(color='#DC2626', width=3)))
            fig_line.add_trace(go.Scatter(x=daily_trend['Date_parsed'], y=daily_trend['S'], mode='lines+markers', name='ค้าง S/K/L', line=dict(color='#F59E0B', width=3)))
            fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_line, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with cc2:
        st.markdown("<div class='glass-panel'><b>📊 Top 5 สาขาเสี่ยงสูง</b><br><span style='font-size:12px; color:#64748B;'>(แดง=ค้าง P | ส้ม=ค้าง S/K/L)</span>", unsafe_allow_html=True)
        fig_bar = go.Figure()
        if not top5_df.empty:
            fig_bar.add_trace(go.Bar(y=top5_df['Branch'], x=top5_df['P'], name='ค้าง P', orientation='h', marker=dict(color='#DC2626')))
            fig_bar.add_trace(go.Bar(y=top5_df['Branch'], x=top5_df['S'], name='ค้าง S/K/L', orientation='h', marker=dict(color='#F59E0B')))
            fig_bar.update_layout(barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Table
    st.markdown("<h4 style='color: #1E293B;'>📋 ML INSIGHTS DATA GRID</h4>", unsafe_allow_html=True)
    st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
    display_df = latest_df[['Branch', 'P', 'S', '⏱️ วันค้าง', '⚠️ SLA Risk']].rename(columns={'Branch': 'สาขา'})
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
