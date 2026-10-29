import gradio as gr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import spaces

# แผนผังกลุ่ม ปจ.
REGION_MAP = {
    "นครราชสีมา": "30xxx นครราชสีมา",
    "บุรีรัมย์": "31xxx บุรีรัมย์",
    "สุรินทร์": "32xxx สุรินทร์",
    "ชัยภูมิ": "36xxx ชัยภูมิ",
    "ร้อยเอ็ด": "45xxx ร้อยเอ็ด"
}

def load_real_data():
    try:
        url = "https://docs.google.com/spreadsheets/d/11COh7oHLLJjsUOBTDmSRQqZADl1oVTZ3HnACcDnacdc/export?format=csv&gid=2062579029"
        df = pd.read_csv(url)
        
        col_date = df.columns[2]     # C: วันที่สุ่มตรวจ
        col_region = df.columns[3]   # D: กลุ่ม ปจ.
        col_zip = df.columns[4]      # E: รหัสไปรษณีย์
        col_branch = df.columns[5]   # F: ที่ทำการ (งานจ่ายสลาก)
        col_p = df.columns[6]        # G: ค้าง P
        col_s = df.columns[7]        # H: ค้าง S/K/L

        df = df.rename(columns={
            col_date: 'Date', col_region: 'Region',
            col_zip: 'Zipcode', col_branch: 'Raw_Branch',
            col_p: 'P', col_s: 'S'
        })
        
        df['Zipcode'] = df['Zipcode'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df['Raw_Branch'] = df['Raw_Branch'].astype(str).str.strip()
        df['Branch'] = df['Zipcode'] + " " + df['Raw_Branch']
        
        # ปรับชื่อกลุ่ม ปจ. ให้มีรหัสนำหน้า เช่น 30xxx นครราชสีมา
        df['Region_Display'] = df['Region'].astype(str).str.strip().map(lambda x: REGION_MAP.get(x, x))
        
        df['P'] = pd.to_numeric(df['P'], errors='coerce').fillna(0)
        df['S'] = pd.to_numeric(df['S'], errors='coerce').fillna(0)
        df['Total'] = df['P'] + df['S']
        df = df[df['Raw_Branch'].notna() & (df['Raw_Branch'] != '') & (df['Raw_Branch'] != 'nan')]
        
        df['Date'] = df['Date'].astype(str).str.strip()
        df['Date_parsed'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce'))
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], errors='coerce'))
        df = df[df['Date_parsed'].notna()]
        return df
    except Exception:
        return pd.DataFrame()

def get_risk_info(total):
    if total >= 100: return ("🔴 สุ่มเสี่ยง", "3.5 วัน", "🔴 95% (สุ่มเสี่ยง)", 1)
    elif total >= 30: return ("🟡 เฝ้าระวัง", "2.1 วัน", "🟡 65% (เฝ้าระวัง)", 2)
    else: return ("🟢 ปกติ", "1.2 วัน", "🟢 15% (ปกติ)", 3)

df_base = load_real_data()

def sync_branch_options(selected_region_display):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty or selected_region_display == "ALL":
        branches = ["ALL"] + sorted(df['Branch'].dropna().unique().tolist())
    else:
        filtered = df[df['Region_Display'] == selected_region_display]
        branches = ["ALL"] + sorted(filtered['Branch'].dropna().unique().tolist())
    return gr.update(choices=branches, value="ALL")

@spaces.GPU
def update_dashboard(selected_time_days, selected_region_display, selected_branch, risk_critical, risk_watch, risk_normal):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty:
        return "", "", "", None, None, pd.DataFrame()

    max_date = df['Date_parsed'].max()
    
    # กำหนด filtered_df ตามช่วงเวลาที่เลือก
    if selected_time_days == 1:
        filtered_df = df[df['Date_parsed'] == max_date].copy()
    else:
        cutoff = max_date - pd.Timedelta(days=selected_time_days)
        filtered_df = df[df['Date_parsed'] >= cutoff].copy()

    if selected_region_display != "ALL":
        filtered_df = filtered_df[filtered_df['Region_Display'] == selected_region_display]
    if selected_branch != "ALL":
        filtered_df = filtered_df[filtered_df['Branch'] == selected_branch]

    latest_df = filtered_df.groupby(['Region_Display', 'Branch'])[['P', 'S', 'Total']].sum().reset_index()
    risk_info = latest_df['Total'].apply(get_risk_info).tolist()
    latest_df['⚠️ SLA Risk'] = [r[0] for r in risk_info]
    latest_df['⏱️ ประเมินวันค้าง'] = [r[1] for r in risk_info]
    latest_df['⚠️ SLA Risk Score'] = [r[2] for r in risk_info]
    latest_df['Risk Code'] = [r[3] for r in risk_info]

    allowed_risks = []
    if risk_critical: allowed_risks.append(1)
    if risk_watch: allowed_risks.append(2)
    if risk_normal: allowed_risks.append(3)
    latest_df = latest_df[latest_df['Risk Code'].isin(allowed_risks)]
    latest_df = latest_df.sort_values(by='Total', ascending=False)

    total_p = int(latest_df['P'].sum()) if not latest_df.empty else 0
    total_s = int(latest_df['S'].sum()) if not latest_df.empty else 0
    risk_branches = len(latest_df[latest_df['Risk Code'] == 1])

    # 1. แบนเนอร์แจ้งเตือน AI Alert
    top_crit = latest_df[latest_df['Risk Code'] == 1]
    if not top_crit.empty:
        crit_branch = top_crit.iloc[0]['Branch']
        banner_html = f"""
        <div class="alert-banner">
            <span style="font-size:15px; font-weight:700;">🚨 AI ALERT BANNER (ระบบแจ้งเตือน SLA อัจฉริยะ) :</span>
            <span>[ 🔴 สุ่มเสี่ยง: ประเมินพบ '{crit_branch}' คาดว่าจะดำเนินการไม่ได้ตามมาตรฐาน SLA ที่ ปณท กำหนด! ]</span>
        </div>
        """
    else:
        banner_html = """
        <div class="alert-banner alert-safe">
            <span style="font-size:15px; font-weight:700;">✅ AI ALERT BANNER (ระบบแจ้งเตือน SLA อัจฉริยะ) :</span>
            <span>[ 🟢 ปกติ: ปริมาณงานจัดส่งสลากฯ ของทุกที่ทำการเป็นไปตามมาตรฐาน SLA ของ ปณท]</span>
        </div>
        """

    level_name = f"{selected_branch}" if selected_branch != "ALL" else (f"{selected_region_display}" if selected_region_display != "ALL" else "ภาพรวม ปข.3")
    kpi_header_html = f"""<div class="section-title">📊 EXECUTIVE KPIs (ข้อมูลระดับ: {level_name})</div>"""

    # 2. Executive KPI Cards
    kpi_cards_html = f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div>
                <div class="kpi-title">📦 ค้าง P (สถานะรอจ่าย)</div>
                <div class="kpi-num">{total_p:,} <span class="kpi-unit">ชิ้น</span></div>
            </div>
            <div class="kpi-badge badge-red">📦</div>
        </div>
        <div class="kpi-card">
            <div>
                <div class="kpi-title">📋 ค้าง S/K/L (รับแล้ว/ส่งคืน)</div>
                <div class="kpi-num">{total_s:,} <span class="kpi-unit">ชิ้น</span></div>
            </div>
            <div class="kpi-badge badge-orange">📋</div>
        </div>
        <div class="kpi-card">
            <div>
                <div class="kpi-title">🚨 สุ่มเสี่ยงตกเกณฑ์ SLA</div>
                <div class="kpi-num">{risk_branches} <span class="kpi-unit">สาขา</span></div>
            </div>
            <div class="kpi-badge badge-darkred">▲</div>
        </div>
    </div>
    """

    # 3. Line Chart ปรับช่วงเวลาตามที่เลือกจริง
    if selected_time_days == 1:
        trend_cutoff = max_date - pd.Timedelta(days=2)
    else:
        trend_cutoff = max_date - pd.Timedelta(days=selected_time_days)

    trend_df = df.copy()
    if selected_region_display != "ALL":
        trend_df = trend_df[trend_df['Region_Display'] == selected_region_display]
    if selected_branch != "ALL":
        trend_df = trend_df[trend_df['Branch'] == selected_branch]

    daily_trend = trend_df[trend_df['Date_parsed'] >= trend_cutoff].groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    
    if not daily_trend.empty:
        date_str_list = daily_trend['Date_parsed'].dt.strftime('%d/%m').tolist()
        p_list = daily_trend['P'].tolist()
        s_list = daily_trend['S'].tolist()

        fig_line.add_trace(go.Scatter(
            x=date_str_list, y=p_list,
            mode='lines+markers', name='ค้าง P (รอจ่าย)',
            line=dict(color='#EF4444', width=2.5),
            marker=dict(size=6, color='#EF4444')
        ))
        
        fig_line.add_trace(go.Scatter(
            x=date_str_list, y=s_list,
            mode='lines+markers', name='ค้าง S/K/L (รับแล้ว/ส่งคืน)',
            line=dict(color='#F59E0B', width=2.5),
            marker=dict(size=6, color='#F59E0B')
        ))

        # เส้นประคาดการณ์ต่อจากวันล่าสุด
        if len(daily_trend) >= 2:
            last_date = daily_trend['Date_parsed'].iloc[-1]
            future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, 4)]
            proj_dates_str = [date_str_list[-1]] + [d.strftime('%d/%m') for d in future_dates]
            x_numeric = np.arange(len(daily_trend))
            
            slope_p, intercept_p = np.polyfit(x_numeric, p_list, 1)
            future_p = [p_list[-1]] + [max(0, slope_p * (len(daily_trend) - 1 + i) + intercept_p) for i in range(1, 4)]
            fig_line.add_trace(go.Scatter(
                x=proj_dates_str, y=future_p,
                mode='lines', name='- - - คาดการณ์ ค้าง P',
                line=dict(color='#EF4444', width=2, dash='dash')
            ))

            slope_s, intercept_s = np.polyfit(x_numeric, s_list, 1)
            future_s = [s_list[-1]] + [max(0, slope_s * (len(daily_trend) - 1 + i) + intercept_s) for i in range(1, 4)]
            fig_line.add_trace(go.Scatter(
                x=proj_dates_str, y=future_s,
                mode='lines', name='- - - คาดการณ์ ค้าง S/K/L',
                line=dict(color='#F59E0B', width=2, dash='dash')
            ))

    fig_line.update_layout(
        template="plotly_white",
        paper_bgcolor='rgba(255,255,255,0.7)',
        plot_bgcolor='rgba(255,255,255,0.5)',
        margin=dict(l=35, r=15, t=25, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, family="Kanit")),
        xaxis=dict(showgrid=True, gridcolor='#E2E8F0', type='category', tickfont=dict(size=10, family="Kanit")),
        yaxis=dict(showgrid=True, gridcolor='#E2E8F0', rangemode='tozero', tickfont=dict(size=10, family="Kanit")),
        height=270
    )

    # 4. Bar Chart Top 5
    top5_plot = latest_df.head(5).iloc[::-1]
    fig_bar = go.Figure()
    if not top5_plot.empty:
        branch_labels = top5_plot['Branch'].astype(str).tolist()
        fig_bar.add_trace(go.Bar(
            y=branch_labels, x=top5_plot['S'].tolist(), 
            name='ค้าง S/K/L (รับแล้ว/ส่งคืน)', orientation='h',
            marker=dict(color='#F59E0B'),
            text=[f"{int(v):,}" if v > 0 else "" for v in top5_plot['S']],
            textposition='inside', insidetextanchor='middle', 
            textfont=dict(color="#FFFFFF", size=10, family="Kanit")
        ))
        fig_bar.add_trace(go.Bar(
            y=branch_labels, x=top5_plot['P'].tolist(), 
            name='ค้าง P', orientation='h',
            marker=dict(color='#EF4444'),
            text=[f"{int(v):,}" if v > 0 else "" for v in top5_plot['P']],
            textposition='inside', insidetextanchor='middle', 
            textfont=dict(color="#FFFFFF", size=10, family="Kanit")
        ))
    fig_bar.update_layout(
        barmode='stack',
        template="plotly_white",
        paper_bgcolor='rgba(255,255,255,0.7)',
        plot_bgcolor='rgba(255,255,255,0.5)',
        margin=dict(l=110, r=15, t=25, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, family="Kanit")),
        xaxis=dict(showgrid=True, gridcolor='#E2E8F0', rangemode='tozero', tickfont=dict(size=10, family="Kanit")),
        yaxis=dict(type='category', showgrid=False, tickfont=dict(size=11, family="Kanit")),
        height=270
    )

    grid_df = latest_df[['Branch', 'P', 'S', '⏱️ ประเมินวันค้าง', '⚠️ SLA Risk Score']].rename(
        columns={'Branch': 'สาขา (ปจ.)', 'P': 'ค้าง P', 'S': 'ค้าง S/K/L', '⏱️ ประเมินวันค้าง': '⏱️ ประเมินวันค้าง', '⚠️ SLA Risk Score': '⚠️ SLA Risk Score'}
    )
    return banner_html, kpi_header_html, kpi_cards_html, fig_line, fig_bar, grid_df

custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap');

* {
    font-family: 'Kanit', sans-serif !important;
}

body, .gradio-container {
    background: linear-gradient(135deg, #d8b4fe 0%, #a5b4fc 50%, #93c5fd 100%) !important;
    min-height: 100vh;
}

/* ================= แผง 3 โลโก้ด้านบน ================= */
.top-logo-container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
    padding: 6px;
    background: rgba(255, 255, 255, 0.5);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.8);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.logo-box {
    flex: 1;
    height: 52px;
    background: #FFFFFF;
    border-radius: 10px;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 3px 5px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    border: 1px solid #E2E8F0;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
}

/* Hover: โลโก้ลอยนูนขึ้น */
.logo-box:hover {
    transform: translateY(-4px) scale(1.05);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
    border-color: #38BDF8;
}

.logo-box img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    pointer-events: none; /* ส่งผ่านการคลิกไปยังลิงก์ <a> */
}

/* ================= Sidebar แผงควบคุม ================= */
.sidebar-panel {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(16px);
    border-radius: 20px !important;
    padding: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.3s ease !important;
}

.sidebar-panel:hover {
    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.08) !important;
}

/* ปุ่มเลือกช่วงเวลา */
.time-radio-grid {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

.time-radio-grid .wrap {
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 6px !important;
}

.time-radio-grid label {
    background: rgba(255, 255, 255, 0.85) !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 6px 2px !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    cursor: pointer !important;
    min-height: 32px !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Hover: ปุ่มช่วงเวลาลอยนูนและเปลี่ยนสี */
.time-radio-grid label:hover {
    background: #FFFFFF !important;
    border-color: #0284C7 !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 4px 10px rgba(2, 132, 199, 0.2) !important;
}

.time-radio-grid label.selected {
    background: #0284C7 !important;
    border-color: #0284C7 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35) !important;
}

.time-radio-grid label.selected span {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

.time-radio-grid span {
    font-size: 11px !important;
    font-weight: 500 !important;
    color: #334155 !important;
}

.time-radio-grid input[type="radio"] {
    display: none !important;
}

/* ================= Header ส่วนหัว ================= */
.main-header {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(16px);
    border-radius: 16px;
    padding: 16px 22px;
    border: 1px solid rgba(255, 255, 255, 0.8);
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
    transition: all 0.3s ease;
}

.main-header:hover {
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.06);
    border-color: rgba(255, 255, 255, 0.95);
}

.title-text {
    font-size: 20px;
    font-weight: 700;
    color: #1E293B;
    margin: 0;
}

.sub-text {
    font-size: 13px;
    color: #64748B;
    margin-top: 4px;
}

.btn-profile {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 13px;
    color: #334155;
    font-weight: 500;
    transition: all 0.25s ease;
}

.btn-profile:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    border-color: #94A3B8;
}

/* ================= Alert Banner ================= */
.alert-banner {
    background: linear-gradient(90deg, #FF4B2B, #FF416C);
    color: #FFFFFF;
    border-radius: 12px;
    padding: 12px 20px;
    font-size: 14px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 12px rgba(255, 75, 43, 0.25);
    transition: all 0.3s ease;
}

.alert-banner:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(255, 75, 43, 0.4);
}

.alert-safe {
    background: linear-gradient(90deg, #10B981, #059669) !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25) !important;
}

.alert-safe:hover {
    box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4) !important;
}

.section-title {
    font-size: 15px;
    font-weight: 700;
    color: #1E293B;
    margin-bottom: 10px;
}

/* ================= การ์ด EXECUTIVE KPIs (ไฮไลต์หลัก) ================= */
.kpi-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 14px;
}

.kpi-card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid rgba(255, 255, 255, 0.9);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
    cursor: pointer;
    /* แอนิเมชันเวลาขยับเมาส์เข้า-ออก */
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Hover: การ์ด KPI นูนลอยขึ้น เปลี่ยนสีขอบและเงา */
.kpi-card:hover {
    transform: translateY(-6px) scale(1.02);
    background: rgba(255, 255, 255, 0.98);
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.12), 0 0 15px rgba(255, 255, 255, 0.6);
    border-color: #FFFFFF;
}

.kpi-title {
    font-size: 13px;
    font-weight: 500;
    color: #64748B;
    transition: color 0.2s ease;
}

.kpi-card:hover .kpi-title {
    color: #334155;
}

.kpi-num {
    font-size: 26px;
    font-weight: 700;
    color: #0F172A;
    margin-top: 4px;
}

.kpi-unit {
    font-size: 15px;
    font-weight: 400;
    color: #64748B;
}

.kpi-badge {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    color: white;
    font-size: 20px;
    transition: transform 0.3s ease;
}

.kpi-card:hover .kpi-badge {
    transform: scale(1.12) rotate(4deg);
}

.badge-red { background: linear-gradient(135deg, #EF4444, #DC2626); }
.badge-orange { background: linear-gradient(135deg, #F59E0B, #D97706); }
.badge-darkred { background: linear-gradient(135deg, #DC2626, #991B1B); font-weight: bold; }

/* ================= กล่องกราฟ & ตาราง (Glass Box) ================= */
.glass-box {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(14px);
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    padding: 16px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Hover: กรอบกราฟและตารางลอยนูนขึ้นมา */
.glass-box:hover {
    transform: translateY(-4px);
    background: rgba(255, 255, 255, 0.88) !important;
    box-shadow: 0 12px 25px rgba(0, 0, 0, 0.08) !important;
    border-color: rgba(255, 255, 255, 0.95) !important;
}

.chart-subtitle {
    font-size: 11px;
    color: #64748B;
    margin-top: -6px;
    margin-bottom: 8px;
    line-height: 1.4;
}

/* ================= ปุ่มกด ================= */
.refresh-btn {
    background: #0284C7 !important;
    color: white !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    border: none !important;
    transition: all 0.25s ease !important;
}

.refresh-btn:hover {
    background: #0369A1 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4) !important;
}

.export-btn {
    background: #FFFFFF !important;
    color: #475569 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    margin-top: 6px !important;
    font-weight: 500 !important;
    transition: all 0.25s ease !important;
}

.export-btn:hover {
    background: #F8FAFC !important;
    color: #0F172A !important;
    border-color: #94A3B8 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06) !important;
}

.legend-box {
    background: rgba(255, 255, 255, 0.8);
    border-radius: 12px;
    padding: 14px 18px;
    font-size: 12px;
    color: #475569;
    border: 1px solid rgba(255, 255, 255, 0.9);
    line-height: 1.6;
    transition: all 0.3s ease;
}

.legend-box:hover {
    background: rgba(255, 255, 255, 0.95);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
}

.dataframe-centered table th,
.dataframe-centered table td {
    text-align: center !important;
    vertical-align: middle !important;
}
"""
region_choices = ["ALL", "30xxx นครราชสีมา", "31xxx บุรีรัมย์", "32xxx สุรินทร์", "36xxx ชัยภูมิ", "45xxx ร้อยเอ็ด"]
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

# แถวที่ 1 ได้ [1 วัน] [1 เดือน] [1 ปี]
# จัดเรียง 3 คอลัมน์: แถวที่ 1 จะได้ [1 วัน] [1 เดือน] [1 ปี] ตรงกันพอดี
time_choices = [
    ("1 วัน", 1), ("1 เดือน", 30), ("1 ปี", 365),
    ("3 วัน", 3), ("3 เดือน", 90), ("", 365),       # ช่องว่างรักษาโครงสร้าง 3 คอลัมน์
    ("7 วัน", 7), ("6 เดือน", 180), ("", 365),
    ("15 วัน", 15), ("", 365), ("", 365)
]
# กรองเอาเฉพาะปุ่มที่มีข้อความจริง
clean_time_choices = [
    ("1 วัน", 1), ("1 เดือน", 30), ("1 ปี", 365),
    ("3 วัน", 3), ("3 เดือน", 90),
    ("7 วัน", 7), ("6 เดือน", 180),
    ("15 วัน", 15)
]

with gr.Blocks(title="ระบบประเมินความเสี่ยงและวิเคราะห์ SLA การให้บริการจัดส่งสลากกินแบ่งรัฐบาล", css=custom_css) as demo:
    
    with gr.Row():
        # ========== แถบซ้าย: แผงควบคุม (SIDEBAR) ==========
        with gr.Column(scale=2, elem_classes=["sidebar-panel"]):
            
            gr.HTML("""
            <div class="top-logo-container">
                <a href="http://10.253.23.3:84/" target="_blank" rel="noopener noreferrer" class="logo-box" title="สลากฯ x ปณท">
                    <img src="https://i.postimg.cc/90G7q1zb/36272783-2092308694112983-4522613958690996224-n.jpg" alt="สลากฯ x ปณท">
                </a>
                <a href="https://www.thailandpost.co.th/th/index/" target="_blank" rel="noopener noreferrer" class="logo-box" title="เว็บไซต์ไปรษณีย์ไทย">
                    <img src="https://i.postimg.cc/kGxbtwDw/480939523-952543977058068-1004086044975536579-n.jpg" alt="เว็บไซต์ไปรษณีย์ไทย">
                </a>
                <a href="http://qms.praisanee.com/Web/Tracking/singleTrackingOld.aspx" target="_blank" rel="noopener noreferrer" class="logo-box" title="QMS ปณท">
                    <img src="https://i.postimg.cc/fyx905kK/Logo-takr-aya-(3).png" alt="QMS ปณท">
                </a>
            </div>
            <div style="font-size:15px; font-weight:700; color:#1E293B; margin-bottom:10px;">⚙️ แผงควบคุม</div>
            <div style="font-size:12px; font-weight:600; color:#475569;">[ 🕒 วิเคราะห์ช่วงเวลา ]</div>
            """)
            
            time_filter = gr.Radio(
                choices=time_choices,
                value=7, label="", show_label=False,
                elem_classes=["time-radio-grid"]
            )
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ 🏢 เลือกกลุ่ม ปจ. ]</div>""")
            region_filter = gr.Dropdown(choices=region_choices, value="ALL", label="", show_label=False)
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ 📍 ชื่อที่ทำการ ]</div>""")
            branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="", show_label=False)
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ ⚠️ ระดับความเสี่ยง ]</div>""")
            with gr.Column():
                risk_crit = gr.Checkbox(value=True, label="🔴 สุ่มเสี่ยง")
                risk_wat = gr.Checkbox(value=True, label="🟡 เฝ้าระวัง")
                risk_norm = gr.Checkbox(value=True, label="🟢 ปกติ")
                
            refresh_btn = gr.Button("🔄 Refresh Data", elem_classes=["refresh-btn"])
            export_btn = gr.Button("📄 Export PDF / JPG", elem_classes=["export-btn"])

        # ========== พื้นที่ขวา: แดชบอร์ดหลัก ==========
        with gr.Column(scale=8):
            gr.HTML("""
            <div class="main-header">
                <div>
                    <div class="title-text">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA การให้บริการจัดส่งสลากกินแบ่งรัฐบาล ในพื้นที่ ปข.3</div>
                    <div class="sub-text">🏢 พัฒนาระบบโดย: <b>สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า</b></div>
                </div>
                <div class="btn-profile">👤 Executive Profile</div>
            </div>
            """)

            alert_banner = gr.HTML()
            kpi_header = gr.HTML()
            kpi_cards = gr.HTML()

            with gr.Column(elem_classes=["glass-box"]):
                gr.HTML("""<div class="section-title">📊 VISUAL ANALYTICS (การปฏิบัติตาม SLA ประจำงวด)</div>""")
                with gr.Row():
                    with gr.Column():
                        gr.HTML("""
                        <div style="font-size:13px; font-weight:600; color:#1E293B;">[ 📈 แนวโน้มการค้าง P vs S/K/L ]</div>
                        <div class="chart-subtitle">(เทียบเส้นเวลาใกล้วันที่ 5 และ 20 ของเดือน (กำหนดจ่ายสลากจองฯ) : บันทึกสถานะ S และกำหนดวันส่งคืนสลากฯ วันที่ 12 และ 27 ของเดือน : บันทึกสถานะ K/L )</div>
                        """)
                        chart_line = gr.Plot()
                    with gr.Column():
                        gr.HTML("""
                        <div style="font-size:13px; font-weight:600; color:#1E293B;">[ 📊 Top 5 สาขาเสี่ยงสูง ]</div>
                        <div class="chart-subtitle">(จำแนกสถานะ: ค้าง P (รอจ่าย ณ ที่ทำการ) -สีแดง | ค้าง S/K/L (ผู้รับได้รับเรียบร้อย/ส่งคืนต้นทาง) -สีส้ม)</div>
                        """)
                        chart_bar = gr.Plot()

            with gr.Column(elem_classes=["glass-box"]):
                gr.HTML("""<div class="section-title">📋 ML INSIGHTS DATA GRID (ตารางข้อมูลการให้บริการ)</div>""")
                table_grid = gr.Dataframe(interactive=False, elem_classes=["dataframe-centered"])

            gr.HTML("""
            <div class="legend-box">
                <b>ℹ️ คำอธิบายเกณฑ์การประเมิน SLA (Rule-based & ML Logic):</b><br>
                • <b>ค้าง P:</b> สถานะ 'รอจ่าย ณ ที่ทำการ' | <b>ค้าง S/K/L:</b> สถานะ 'ผู้รับได้รับเรียบร้อย/รอส่งคืน/ส่งต่อ' (ระบุตามสถานะระบบ QMS-ปณท)<br>
                • <span style="color:#DC2626;">🔴 สุ่มเสี่ยง:</span> ยอดค้างสะสม ≥ 100 ชิ้น หรือ ประมาณการตกค้างสะสมเกิน 3 วัน หรือ ประเมินมีความเสี่ยงตกเกณฑ์มาตรฐานอย่างยิ่ง<br>
                • <span style="color:#D97706;">🟡 เฝ้าระวัง:</span> ยอดสะสม 30-99 ชิ้น หรือ คาดการณ์ตกค้าง 2-3 วัน หรือ มีแนวโน้มการนำจ่ายช้ากว่ากรอบเวลา
            </div>
            """)

    inputs = [time_filter, region_filter, branch_filter, risk_crit, risk_wat, risk_norm]
    outputs = [alert_banner, kpi_header, kpi_cards, chart_line, chart_bar, table_grid]

    region_filter.change(fn=sync_branch_options, inputs=[region_filter], outputs=[branch_filter])

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    time_filter.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    region_filter.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    branch_filter.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    risk_crit.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    risk_wat.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    risk_norm.change(fn=update_dashboard, inputs=inputs, outputs=outputs)
    
    export_btn.click(fn=None, js="() => { window.print(); }")

    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
