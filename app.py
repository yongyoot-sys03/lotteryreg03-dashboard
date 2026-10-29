import gradio as gr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import spaces

def load_real_data():
    try:
        url = "https://docs.google.com/spreadsheets/d/11COh7oHLLJjsUOBTDmSRQqZADl1oVTZ3HnACcDnacdc/export?format=csv&gid=2062579029"
        df = pd.read_csv(url)
        
        # แมปคอลัมน์จาก Sheet
        # คอลัมน์ 1: Zipcode/รหัสไปรษณีย์, 2: Date, 3: Region, 5: Branch, 6: P, 7: S
        col_zip = df.columns[1] if len(df.columns) > 1 else None
        col_date = df.columns[2]
        col_region = df.columns[3]
        col_branch = df.columns[5]
        col_p = df.columns[6]
        col_s = df.columns[7]

        df = df.rename(columns={
            col_date: 'Date', col_region: 'Region', 
            col_branch: 'Raw_Branch', col_p: 'P', col_s: 'S'
        })
        if col_zip:
            df = df.rename(columns={col_zip: 'Zipcode'})
            df['Zipcode'] = df['Zipcode'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df['Branch'] = df['Zipcode'] + " " + df['Raw_Branch'].astype(str).str.strip()
        else:
            df['Branch'] = df['Raw_Branch'].astype(str).str.strip()

        df['P'] = pd.to_numeric(df['P'], errors='coerce').fillna(0)
        df['S'] = pd.to_numeric(df['S'], errors='coerce').fillna(0)
        df['Total'] = df['P'] + df['S']
        df = df[df['Raw_Branch'].notna() & (df['Raw_Branch'] != '')]
        
        df['Date'] = df['Date'].astype(str).str.strip()
        df['Date_parsed'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce'))
        df['Date_parsed'] = df['Date_parsed'].fillna(pd.to_datetime(df['Date'], errors='coerce'))
        df = df[df['Date_parsed'].notna()]
        return df
    except Exception:
        return pd.DataFrame()

def get_risk_info(total):
    if total >= 100: return ("🔴 วิกฤต", "3.5 วัน", "🔴 95% (วิกฤต)", 1)
    elif total >= 30: return ("🟡 เฝ้าระวัง", "2.1 วัน", "🟡 65% (เฝ้าระวัง)", 2)
    else: return ("🟢 ปกติ", "1.2 วัน", "🟢 15% (ปกติ)", 3)

df_base = load_real_data()

def sync_branch_options(selected_region):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty or selected_region == "ALL":
        branches = ["ALL"] + sorted(df['Branch'].dropna().unique().tolist())
    else:
        filtered = df[df['Region'] == selected_region]
        branches = ["ALL"] + sorted(filtered['Branch'].dropna().unique().tolist())
    return gr.update(choices=branches, value="ALL")

@spaces.GPU
def update_dashboard(selected_time_days, selected_region, selected_branch, risk_critical, risk_watch, risk_normal):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty:
        return "", "", "", None, None, pd.DataFrame()

    max_date = df['Date_parsed'].max()
    if selected_time_days == 1:
        filtered_df = df[df['Date_parsed'] == max_date]
    else:
        cutoff = max_date - pd.Timedelta(days=selected_time_days)
        filtered_df = df[df['Date_parsed'] >= cutoff]

    if selected_region != "ALL":
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    if selected_branch != "ALL":
        filtered_df = filtered_df[filtered_df['Branch'] == selected_branch]

    latest_df = filtered_df.groupby(['Region', 'Branch'])[['P', 'S', 'Total']].sum().reset_index()
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
            <span>[ 🔴 วิกฤต: ประเมินพบ 'ที่ทำการ {crit_branch}' คาดว่าจะจัดส่งสลากฯ ไม่ได้ตามมาตรฐาน SLA ที่ ปณท. กำหนด! ]</span>
        </div>
        """
    else:
        banner_html = """
        <div class="alert-banner alert-safe">
            <span style="font-size:15px; font-weight:700;">✅ AI ALERT BANNER (ระบบแจ้งเตือน SLA อัจฉริยะ) :</span>
            <span>[ 🟢 ปกติ: ปริมาณงานจัดส่งสลากฯ ของทุกที่ทำการเป็นไปตามมาตรฐาน SLA ของ ปณท. ]</span>
        </div>
        """

    level_name = f"{selected_branch}" if selected_branch != "ALL" else (f"กลุ่ม ปจ.{selected_region}" if selected_region != "ALL" else "ภาพรวม ปข.3")
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
                <div class="kpi-title">🚨 สาขาตกเกณฑ์ SLA</div>
                <div class="kpi-num">{risk_branches} <span class="kpi-unit">สาขา</span></div>
            </div>
            <div class="kpi-badge badge-darkred">▲</div>
        </div>
    </div>
    """

    # 3. Line Chart พร้อมเส้นประแนวโน้มประมาณการ (Trendline Projection)
    trend_cutoff = max_date - pd.Timedelta(days=max(selected_time_days, 15))
    trend_df = df.copy()
    if selected_region != "ALL":
        trend_df = trend_df[trend_df['Region'] == selected_region]
    if selected_branch != "ALL":
        trend_df = trend_df[trend_df['Branch'] == selected_branch]

    daily_trend = trend_df[trend_df['Date_parsed'] >= trend_cutoff].groupby('Date_parsed')[['P', 'S', 'Total']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    
    if not daily_trend.empty:
        date_labels = daily_trend['Date_parsed'].dt.strftime('%d/%m')
        
        # เส้นจริงค้าง P
        fig_line.add_trace(go.Scatter(
            x=date_labels, y=daily_trend['P'],
            mode='lines+markers', name='ค้าง P',
            line=dict(color='#EF4444', width=2.5),
            marker=dict(size=6, color='#EF4444')
        ))
        # เส้นจริงค้าง S/K/L
        fig_line.add_trace(go.Scatter(
            x=date_labels, y=daily_trend['S'],
            mode='lines+markers', name='ค้าง S/K/L (รับแล้ว/ส่งคืน)',
            line=dict(color='#F59E0B', width=2.5),
            marker=dict(size=6, color='#F59E0B')
        ))
        
        # เส้นประบอกแนวโน้มประมาณการยอดรวม (Linear Trendline Projection)
        if len(daily_trend) >= 2:
            x_vals = np.arange(len(daily_trend))
            y_vals = daily_trend['Total'].values
            slope, intercept = np.polyfit(x_vals, y_vals, 1)
            trend_y = [max(0, slope * x + intercept) for x in x_vals]
            
            fig_line.add_trace(go.Scatter(
                x=date_labels, y=trend_y,
                mode='lines', name='- - - เส้นประแนวโน้มประมาณการ',
                line=dict(color='#64748B', width=2, dash='dash')
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

    # 4. Bar Chart Top 5 (ดึงสาขารหัส+ชื่อ ตรงกับตาราง)
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
        margin=dict(l=90, r=15, t=25, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, family="Kanit")),
        xaxis=dict(showgrid=True, gridcolor='#E2E8F0', rangemode='tozero', tickfont=dict(size=10, family="Kanit")),
        yaxis=dict(type='category', showgrid=False, tickfont=dict(size=11, family="Kanit")),
        height=270
    )

    grid_df = latest_df[['Branch', 'P', 'S', '⏱️ ประเมินวันค้าง', '⚠️ SLA Risk Score']].rename(
        columns={'Branch': 'สาขา (ปจ.)', 'P': 'ค้าง P', 'S': 'ค้าง S/K/L', '⏱️ ประเมินวันค้าง': '⏱️ ประเมินวันค้าง', '⚠️ SLA Risk Score': '⚠️ SLA Risk Score'}
    )
    return banner_html, kpi_header_html, kpi_cards_html, fig_line, fig_bar, grid_df

# CSS สไตล์ Glassmorphism พร้อมการจัดภาพโลโก้ตรงกลาง
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap');

* {
    font-family: 'Kanit', sans-serif !important;
}

body, .gradio-container {
    background: linear-gradient(135deg, #d8b4fe 0%, #a5b4fc 50%, #93c5fd 100%) !important;
    min-height: 100vh;
}

/* แผง 3 โลโก้จริง จัดกึ่งกลาง ขยายใหญ่เต็มที่ */
.top-logo-container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding: 8px;
    background: rgba(255, 255, 255, 0.5);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.8);
}

.logo-box {
    flex: 1;
    height: 56px;
    background: #FFFFFF;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 4px 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #E2E8F0;
}

.logo-box img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

/* Sidebar แผงควบคุม */
.sidebar-panel {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(16px);
    border-radius: 20px !important;
    padding: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05) !important;
}

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
    margin-top: 2px;
}

.btn-profile {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 13px;
    color: #334155;
    font-weight: 500;
}

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
}

.alert-safe {
    background: linear-gradient(90deg, #10B981, #059669) !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25) !important;
}

.section-title {
    font-size: 15px;
    font-weight: 700;
    color: #1E293B;
    margin-bottom: 10px;
}

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
}

.kpi-title {
    font-size: 13px;
    font-weight: 500;
    color: #64748B;
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
}

.badge-red { background: linear-gradient(135deg, #EF4444, #DC2626); }
.badge-orange { background: linear-gradient(135deg, #F59E0B, #D97706); }
.badge-darkred { background: linear-gradient(135deg, #DC2626, #991B1B); font-weight: bold; }

.glass-box {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(14px);
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    padding: 16px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03) !important;
}

.chart-subtitle {
    font-size: 11px;
    color: #64748B;
    margin-top: -6px;
    margin-bottom: 8px;
}

.refresh-btn {
    background: #0284C7 !important;
    color: white !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    border: none !important;
}

.export-btn {
    background: #FFFFFF !important;
    color: #475569 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    margin-top: 6px !important;
    font-weight: 500 !important;
}

.legend-box {
    background: rgba(255, 255, 255, 0.8);
    border-radius: 12px;
    padding: 14px 18px;
    font-size: 12px;
    color: #475569;
    border: 1px solid rgba(255, 255, 255, 0.9);
    line-height: 1.6;
}
"""

region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

with gr.Blocks(title="ระบบประเมินความเสี่ยงและวิเคราะห์ SLA การให้บริการจัดส่งสลากกินแบ่งรัฐบาล", css=custom_css) as demo:
    
    with gr.Row():
        # ========== แถบซ้าย: แผงควบคุม (SIDEBAR) ==========
        with gr.Column(scale=2, elem_classes=["sidebar-panel"]):
            
            # โลโก้ 3 รูปจริง ขยายใหญ่และจัดกึ่งกลาง
            gr.HTML("""
            <div class="top-logo-container">
                <div class="logo-box">
                    <img src="https://i.postimg.cc/90G7q1zb/36272783-2092308694112983-4522613958690996224-n.jpg" alt="Logo 1">
                </div>
                <div class="logo-box">
                    <img src="https://i.postimg.cc/kGxbtwDw/480939523-952543977058068-1004086044975536579-n.jpg" alt="Logo 2">
                </div>
                <div class="logo-box">
                    <img src="https://i.postimg.cc/fyx905kK/Logo-takr-aya-(3).png" alt="Logo 3">
                </div>
            </div>
            <div style="font-size:15px; font-weight:700; color:#1E293B; margin-bottom:10px;">⚙️ แผงควบคุม</div>
            <div style="font-size:12px; font-weight:600; color:#475569;">[ 🕒 วิเคราะห์ช่วงเวลา ]</div>
            """)
            
            time_filter = gr.Radio(
                choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90), ("6 เดือน", 180), ("1 ปี", 365)],
                value=7, label="", show_label=False
            )
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ 🏢 เลือกกลุ่ม ปจ. ]</div>""")
            region_filter = gr.Dropdown(choices=region_list, value="ALL", label="", show_label=False)
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ 📍 ชื่อที่ทำการ ]</div>""")
            branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="", show_label=False)
            
            gr.HTML("""<div style="font-size:12px; font-weight:600; color:#475569; margin-top:10px;">[ ⚠️ ระดับความเสี่ยง ]</div>""")
            with gr.Column():
                risk_crit = gr.Checkbox(value=True, label="🔴 วิกฤต")
                risk_wat = gr.Checkbox(value=True, label="🟡 เฝ้าระวัง")
                risk_norm = gr.Checkbox(value=True, label="🟢 ปกติ")
                
            refresh_btn = gr.Button("🔄 Refresh Data", elem_classes=["refresh-btn"])
            export_btn = gr.Button("📄 Export PDF / JPG", elem_classes=["export-btn"])

        # ========== พื้นที่ขวา: แดชบอร์ดหลัก ==========
        with gr.Column(scale=8):
            gr.HTML("""
            <div class="main-header">
                <div>
                    <div class="title-text">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA การให้บริการจัดส่งสลากกินแบ่งรัฐบาล</div>
                    <div class="sub-text">🏢 หน่วยงานรับผิดชอบ: <b>สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า</b></div>
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
                        <div class="chart-subtitle">(เทียบเส้นเวลาใกล้วันที่ 5 และ 20 ของเดือน เพื่อดูความสามารถในการระบายสลากฯ)</div>
                        """)
                        chart_line = gr.Plot()
                    with gr.Column():
                        gr.HTML("""
                        <div style="font-size:13px; font-weight:600; color:#1E293B;">[ 📊 Top 5 สาขาเสี่ยงสูง ]</div>
                        <div class="chart-subtitle">(แสดงสาขาที่มียอดค้างสะสมสูงสุด เพื่อวางแผนสนับสนุนกำลังพลนำจ่าย)</div>
                        """)
                        chart_bar = gr.Plot()

            with gr.Column(elem_classes=["glass-box"]):
                gr.HTML("""<div class="section-title">📋 ML INSIGHTS DATA GRID (ตารางข้อมูลการให้บริการ)</div>""")
                table_grid = gr.Dataframe(interactive=False)

            gr.HTML("""
            <div class="legend-box">
                <b>ℹ️ คำอธิบายเกณฑ์การประเมิน SLA (Rule-based & ML Logic):</b><br>
                • <b>ค้าง P:</b> สถานะ 'รอจ่าย ณ ที่ทำการ' | <b>ค้าง S/K/L:</b> สถานะ 'ผู้รับได้รับเรียบร้อย/รอส่งคืน/ส่งต่อ' (ระบุตามสถานะระบบ ปณท.)<br>
                • <span style="color:#DC2626;">🔴 วิกฤต:</span> ยอดค้างสะสม ≥ 100 ชิ้น หรือ ประมาณการตกค้างสะสมเกิน 3 วัน หรือ ประเมินมีความเสี่ยงตกเกณฑ์มาตรฐานอย่างยิ่ง<br>
                • <span style="color:#D97706;">🟡 เฝ้าระวัง:</span> ยอดสะสม 30-99 ชิ้น หรือ คาดการณ์ตกค้าง 2-3 วัน หรือ มีแนวโน้มการนำจ่ายช้ากว่ากรอบเวลา
            </div>
            """)

    inputs = [time_filter, region_filter, branch_filter, risk_crit, risk_wat, risk_norm]
    outputs = [alert_banner, kpi_header, kpi_cards, chart_line, chart_bar, table_grid]

    # การผูก Event อัปเดต Dropdown สาขาตามกลุ่ม ปจ.
    region_filter.change(fn=sync_branch_options, inputs=[region_filter], outputs=[branch_filter])

    # Event อัปเดตหน้า Dashboard
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
