import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import spaces

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
    except Exception:
        return pd.DataFrame()

def get_risk_info(total):
    if total >= 100: return ("🔴 วิกฤต (หลุด SLA)", "3.5 วัน", 1)
    elif total >= 30: return ("🟡 เฝ้าระวังใกล้ชิด", "2.1 วัน", 2)
    else: return ("🟢 ปกติคล่องตัว", "1.2 วัน", 3)

df_base = load_real_data()

@spaces.GPU
def update_dashboard(selected_time_days, selected_region, selected_branch):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty:
        return "<div class='banner-alert safe'>⚠️ ไม่สามารถดึงข้อมูลได้</div>", "", None, None, pd.DataFrame()

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
    latest_df['⏱️ คาดการณ์ค้าง'] = [r[1] for r in risk_info]
    latest_df['Risk Code'] = [r[2] for r in risk_info]
    latest_df = latest_df.sort_values(by='Total', ascending=False)

    total_p = int(latest_df['P'].sum()) if not latest_df.empty else 0
    total_s = int(latest_df['S'].sum()) if not latest_df.empty else 0
    grand_total = total_p + total_s
    pct_p = (total_p / grand_total * 100) if grand_total > 0 else 0
    pct_s = (total_s / grand_total * 100) if grand_total > 0 else 0
    risk_branches = len(latest_df[latest_df['Risk Code'] == 1])

    top5 = latest_df.head(5).sort_values(by='Total', ascending=True)
    
    # 1. แบนเนอร์เตือนภัย AI Alert
    if not top5.empty and top5.iloc[-1]['Total'] >= 100:
        critical_branch = top5.iloc[-1]['Branch']
        crit_qty = int(top5.iloc[-1]['Total'])
        banner_html = f"""
        <div class="banner-alert critical">
            <div class="radar-dot"></div>
            <div>
                <strong>CRITICAL SLA BREACH ALERT:</strong> ที่ทำการ <u>สาขา{critical_branch}</u> มีสลากฯ สะสมตกค้างรวม <b>{crit_qty:,}</b> ชิ้น เกินเกณฑ์มาตรฐาน! แนะนำเร่งรัดเจ้าหน้าที่นำจ่ายทันที
            </div>
        </div>
        """
    else:
        banner_html = """
        <div class="banner-alert safe">
            <div class="radar-dot safe-dot"></div>
            <div><strong>ALL SYSTEMS OPTIMAL:</strong> ปริมาณการนำจ่ายอยู่ในเกณฑ์ SLA มาตรฐาน ไม่พบสาขาที่มีความเสี่ยงสะสมวิกฤต</div>
        </div>
        """

    # 2. Executive Cards พร้อม Progress Bar
    kpis_html = f"""
    <div class="kpi-grid">
        <div class="kpi-card card-red">
            <div class="kpi-header">
                <span class="kpi-label">📦 ค้าง P (รอการนำจ่าย)</span>
                <span class="kpi-icon">📦</span>
            </div>
            <div class="kpi-value">{total_p:,} <span class="unit">ชิ้น</span></div>
            <div class="progress-bg"><div class="progress-fill fill-red" style="width: {pct_p:.1f}%;"></div></div>
            <div class="kpi-meta">สัดส่วน {pct_p:.1f}% ของยอดตกค้างทั้งหมด</div>
        </div>

        <div class="kpi-card card-amber">
            <div class="kpi-header">
                <span class="kpi-label">📝 ค้าง S/K/L (รับแล้ว/รอส่งคืน)</span>
                <span class="kpi-icon">📝</span>
            </div>
            <div class="kpi-value">{total_s:,} <span class="unit">ชิ้น</span></div>
            <div class="progress-bg"><div class="progress-fill fill-amber" style="width: {pct_s:.1f}%;"></div></div>
            <div class="kpi-meta">สัดส่วน {pct_s:.1f}% ของยอดตกค้างทั้งหมด</div>
        </div>

        <div class="kpi-card card-cyan">
            <div class="kpi-header">
                <span class="kpi-label">🚨 ที่ทำการเสี่ยงหลุด SLA</span>
                <span class="kpi-icon">⚡</span>
            </div>
            <div class="kpi-value">{risk_branches} <span class="unit">แห่ง</span></div>
            <div class="progress-bg"><div class="progress-fill fill-cyan" style="width: {min(risk_branches*10, 100)}%;"></div></div>
            <div class="kpi-meta">จากทั้งหมด {len(latest_df):,} สาขาที่มีการนำจ่าย</div>
        </div>
    </div>
    """

    # 3. กราฟเส้นแบบ Neon Cyber-line Chart
    daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    if not daily_trend.empty:
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['P'],
            mode='lines+markers', name='ค้าง P (รอจ่าย)',
            line=dict(color='#FF3366', width=4, shape='spline'),
            marker=dict(size=8, color='#FF3366', line=dict(width=2, color='#FFFFFF')),
            fill='tozeroy', fillcolor='rgba(255, 51, 102, 0.08)'
        ))
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['S'],
            mode='lines+markers', name='ค้าง S/K/L',
            line=dict(color='#FFAA00', width=4, shape='spline'),
            marker=dict(size=8, color='#FFAA00', line=dict(width=2, color='#FFFFFF')),
            fill='tozeroy', fillcolor='rgba(255, 170, 0, 0.05)'
        ))
    fig_line.update_layout(
        paper_bgcolor='rgba(15, 23, 42, 0.7)',
        plot_bgcolor='rgba(15, 23, 42, 0.4)',
        margin=dict(l=20, r=20, t=40, b=20),
        title=dict(text="<b>📈 ไทม์ไลน์แนวโน้มสลากสะสม (P vs S/K/L)</b>", font=dict(family="Kanit", size=15, color="#F1F5F9")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#CBD5E1")),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.08)', tickfont=dict(family="Kanit", color="#94A3B8")),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.08)', tickfont=dict(family="Kanit", color="#94A3B8")),
    )

    # 4. กราฟแท่ง Top 5 พร้อมข้อความตัวเลขระบุบนแท่ง
    fig_bar = go.Figure()
    if not top5.empty:
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['P'], name='ค้าง P', orientation='h',
            marker=dict(color='#FF3366', line=dict(color='rgba(255,255,255,0.4)', width=1)),
            text=top5['P'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF", family="Kanit")
        ))
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['S'], name='ค้าง S/K/L', orientation='h',
            marker=dict(color='#FFAA00', line=dict(color='rgba(255,255,255,0.4)', width=1)),
            text=top5['S'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF", family="Kanit")
        ))
    fig_bar.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(15, 23, 42, 0.7)',
        plot_bgcolor='rgba(15, 23, 42, 0.4)',
        margin=dict(l=20, r=20, t=40, b=20),
        title=dict(text="<b>📊 5 สาขาสูงสุดที่ต้องเร่งรัด</b>", font=dict(family="Kanit", size=15, color="#F1F5F9")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#CBD5E1")),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.08)', tickfont=dict(family="Kanit", color="#94A3B8")),
        yaxis=dict(tickfont=dict(family="Kanit", color="#F8FAFC")),
    )

    grid_df = latest_df[['Branch', 'P', 'S', 'Total', '⏱️ คาดการณ์ค้าง', '⚠️ SLA Risk']].rename(
        columns={'Branch': 'ที่ทำการไปรษณีย์', 'Total': 'รวมสลากค้างสะสม'}
    )
    return banner_html, kpis_html, fig_line, fig_bar, grid_df

# CSS สไตล์ Executive Dark Glow + Glassmorphism
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700;800&family=Chakra+Petch:wght@500;700&display=swap');

* {
    font-family: 'Kanit', sans-serif !important;
}

body, .gradio-container {
    background: radial-gradient(circle at 10% 20%, #0f172a 0%, #020617 90%) !important;
    color: #F8FAFC !important;
    min-height: 100vh;
}

/* Header Box */
.header-box {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-left: 6px solid #38BDF8;
    border-radius: 20px;
    padding: 24px 30px;
    margin-bottom: 22px;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.header-title {
    font-size: 26px;
    font-weight: 800;
    background: linear-gradient(90deg, #FFFFFF, #93C5FD);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: 0.5px;
}

.header-sub {
    font-size: 14px;
    color: #94A3B8;
    margin-top: 8px;
    display: flex;
    gap: 15px;
    align-items: center;
}

.header-badge {
    background: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

/* แผงกรองข้อมูล */
.filter-box {
    background: rgba(30, 41, 59, 0.5) !important;
    backdrop-filter: blur(12px);
    border-radius: 18px !important;
    padding: 16px 20px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3) !important;
    margin-bottom: 20px !important;
}

/* ปุ่มวิเคราะห์ข้อมูล */
button.primary-btn {
    background: linear-gradient(135deg, #0284C7 0%, #2563EB 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4) !important;
    transition: all 0.2s ease !important;
}

button.primary-btn:hover {
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.7) !important;
    transform: translateY(-2px);
}

/* กล่องเตือน Alert */
.banner-alert {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 16px 24px;
    border-radius: 16px;
    font-size: 15px;
    margin-bottom: 22px;
    backdrop-filter: blur(10px);
}

.banner-alert.critical {
    background: linear-gradient(90deg, rgba(239, 68, 68, 0.25) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(239, 68, 68, 0.6);
    color: #FECACA;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
}

.banner-alert.safe {
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(34, 197, 94, 0.5);
    color: #BBF7D0;
}

.radar-dot {
    width: 12px;
    height: 12px;
    background-color: #EF4444;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
    animation: pulse-red 1.6s infinite;
}

.safe-dot {
    background-color: #22C55E;
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
    animation: pulse-green 1.6s infinite;
}

@keyframes pulse-red {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

@keyframes pulse-green {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

/* KPI Cards แบบ Glow */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-bottom: 24px;
}

.kpi-card {
    background: rgba(30, 41, 59, 0.55);
    backdrop-filter: blur(14px);
    border-radius: 20px;
    padding: 22px 26px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    position: relative;
    overflow: hidden;
    transition: transform 0.25s ease, border-color 0.25s ease;
}

.kpi-card:hover {
    transform: translateY(-4px);
    border-color: rgba(255, 255, 255, 0.25);
}

.kpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.kpi-label {
    font-size: 14px;
    font-weight: 500;
    color: #94A3B8;
}

.kpi-icon {
    font-size: 24px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.kpi-value {
    font-family: 'Chakra Petch', sans-serif !important;
    font-size: 38px;
    font-weight: 700;
    margin: 10px 0 12px 0;
    color: #FFFFFF;
}

.kpi-value .unit {
    font-size: 15px;
    font-weight: 400;
    color: #94A3B8;
}

.progress-bg {
    width: 100%;
    height: 6px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 8px;
}

.progress-fill {
    height: 100%;
    border-radius: 6px;
}

.fill-red { background: linear-gradient(90deg, #FF4757, #FF6B81); }
.fill-amber { background: linear-gradient(90deg, #FFA502, #FFC048); }
.fill-cyan { background: linear-gradient(90deg, #00D2D3, #54A0FF); }

.kpi-meta {
    font-size: 12px;
    color: #64748B;
}

.card-red::after { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: #FF4757; }
.card-amber::after { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: #FFA502; }
.card-cyan::after { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: #00D2D3; }

/* Custom Datatable */
.dataframe-wrap {
    border-radius: 16px !important;
    overflow: hidden !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    background: rgba(30, 41, 59, 0.4) !important;
}
"""

region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

with gr.Blocks(title="Executive SLA Command Center ปข.3", css=custom_css) as demo:
    # 1. Header
    gr.HTML("""
    <div class="header-box">
        <h1 class="header-title">⚡ EXECUTIVE SLA REAL-TIME MONITORING</h1>
        <div class="header-sub">
            <span>📦 ระบบติดตามและวิเคราะห์ความเสี่ยง SLA สลากกินแบ่งรัฐบาล</span>
            <span class="header-badge">ปข.3 | ปณท</span>
        </div>
    </div>
    """)

    # 2. Controls
    with gr.Row(elem_classes=["filter-box"]):
        time_filter = gr.Dropdown(
            choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90)],
            value=7, label="🕒 ช่วงเวลาวิเคราะห์"
        )
        region_filter = gr.Dropdown(choices=region_list, value="ALL", label="🏢 พื้นที่สังกัด (กลุ่ม ปจ.)")
        branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="📍 ที่ทำการไปรษณีย์")
        refresh_btn = gr.Button("⚡ วิเคราะห์ข้อมูลเชิงลึก", variant="primary", elem_classes=["primary-btn"])

    # 3. Dynamic Alert Banner
    alert_box = gr.HTML()

    # 4. KPI Glow Cards
    kpi_box = gr.HTML()

    # 5. Visual Charts
    with gr.Row():
        chart_line = gr.Plot(label="แนวโน้มระยะเวลา")
        chart_bar = gr.Plot(label="จัดอันดับความเสี่ยงสะสม")

    # 6. Detailed Table
    gr.HTML("<h3 style='margin: 20px 0 8px 0; color:#F8FAFC;'>📋 บัญชีข้อมูลและระดับความเสี่ยงรายที่ทำการ</h3>")
    table_grid = gr.Dataframe(interactive=False, elem_classes=["dataframe-wrap"])

    inputs = [time_filter, region_filter, branch_filter]
    outputs = [alert_box, kpi_box, chart_line, chart_bar, table_grid]

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
