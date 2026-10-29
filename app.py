import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import spaces

# โหลดข้อมูลจริงจาก Google Sheets
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
    if total >= 100: return ("🔴 วิกฤต", "3.5 วัน", 1)
    elif total >= 30: return ("🟡 เฝ้าระวัง", "2.1 วัน", 2)
    else: return ("🟢 ปกติ", "1.2 วัน", 3)

df_base = load_real_data()

@spaces.GPU
def update_dashboard(selected_time_days, selected_region, selected_branch):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty:
        empty_banner = "<div class='banner-alert safe'>⚠️ ไม่สามารถดึงข้อมูลได้</div>"
        empty_kpi = "<div class='kpi-container'></div>"
        return empty_banner, empty_kpi, None, None, pd.DataFrame()

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
    latest_df['⏱️ วันค้าง'] = [r[1] for r in risk_info]
    latest_df['Risk Code'] = [r[2] for r in risk_info]
    latest_df = latest_df.sort_values(by='Total', ascending=False)

    total_p = int(latest_df['P'].sum()) if not latest_df.empty else 0
    total_s = int(latest_df['S'].sum()) if not latest_df.empty else 0
    risk_branches = len(latest_df[latest_df['Risk Code'] == 1])

    top5 = latest_df.head(5).sort_values(by='Total', ascending=True)
    
    # 1. กล่องแจ้งเตือนความเสี่ยงฉุกเฉิน
    if not top5.empty and top5.iloc[-1]['Total'] >= 100:
        critical_branch = top5.iloc[-1]['Branch']
        banner_html = f"""
        <div class="banner-alert critical">
            <span class="pulse-icon">🚨</span>
            <div>
                <strong>AI SLA ALERT:</strong> ประเมินพบ <u>สาขา{critical_branch}</u> มีปริมาณตกค้างสะสมเข้าขั้นวิกฤต เสี่ยงหลุดเกณฑ์มาตรฐานจัดส่งสลากฯ!
            </div>
        </div>
        """
    else:
        banner_html = """
        <div class="banner-alert safe">
            <span>🟢</span>
            <div><strong>สถานะปกติ:</strong> ทุกที่ทำการในพื้นที่ที่เลือก ควบคุมปริมาณงานตามกรอบเวลา SLA ได้ตามเกณฑ์</div>
        </div>
        """

    # 2. การ์ด KPI แบบพรีเมียม (Glassmorphism & Gradient)
    kpis_html = f"""
    <div class="kpi-grid">
        <div class="kpi-card card-red">
            <div class="kpi-info">
                <span class="kpi-label">ค้าง P (รอการนำจ่าย)</span>
                <span class="kpi-value">{total_p:,} <small>ชิ้น</small></span>
            </div>
            <div class="kpi-icon">📦</div>
        </div>
        <div class="kpi-card card-amber">
            <div class="kpi-info">
                <span class="kpi-label">ค้าง S/K/L (รับแล้ว/ส่งคืน)</span>
                <span class="kpi-value">{total_s:,} <small>ชิ้น</small></span>
            </div>
            <div class="kpi-icon">📝</div>
        </div>
        <div class="kpi-card card-purple">
            <div class="kpi-info">
                <span class="kpi-label">สาขาวิกฤตเสี่ยงตก SLA</span>
                <span class="kpi-value">{risk_branches} <small>แห่ง</small></span>
            </div>
            <div class="kpi-icon">⚠️</div>
        </div>
    </div>
    """

    # 3. กราฟเส้นแนวโน้ม (Plotly Styled)
    daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    if not daily_trend.empty:
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['P'],
            mode='lines+markers', name='ค้าง P (รอจ่าย)',
            line=dict(color='#FF4757', width=3.5, shape='spline'),
            marker=dict(size=8, color='#FF4757', line=dict(width=2, color='#FFFFFF'))
        ))
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['S'],
            mode='lines+markers', name='ค้าง S/K/L',
            line=dict(color='#FFA502', width=3.5, shape='spline'),
            marker=dict(size=8, color='#FFA502', line=dict(width=2, color='#FFFFFF'))
        ))
    fig_line.update_layout(
        paper_bgcolor='rgba(255,255,255,0.7)',
        plot_bgcolor='rgba(255,255,255,0.3)',
        margin=dict(l=15, r=15, t=35, b=15),
        title=dict(text="<b>📈 แนวโน้มการค้าง P vs S/K/L รายวัน</b>", font=dict(family="Kanit", size=15, color="#1e293b")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)', tickfont=dict(family="Kanit")),
        yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)', tickfont=dict(family="Kanit")),
    )

    # 4. กราฟแท่ง Top 5 (Plotly Styled)
    fig_bar = go.Figure()
    if not top5.empty:
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['P'], name='ค้าง P', orientation='h',
            marker=dict(color='#FF4757', line=dict(color='rgba(255,255,255,0.8)', width=1))
        ))
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['S'], name='ค้าง S/K/L', orientation='h',
            marker=dict(color='#FFA502', line=dict(color='rgba(255,255,255,0.8)', width=1))
        ))
    fig_bar.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(255,255,255,0.7)',
        plot_bgcolor='rgba(255,255,255,0.3)',
        margin=dict(l=15, r=15, t=35, b=15),
        title=dict(text="<b>📊 Top 5 สาขาเสี่ยงสูงสะสม</b>", font=dict(family="Kanit", size=15, color="#1e293b")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)', tickfont=dict(family="Kanit")),
        yaxis=dict(tickfont=dict(family="Kanit")),
    )

    grid_df = latest_df[['Branch', 'P', 'S', 'Total', '⏱️ วันค้าง', '⚠️ SLA Risk']].rename(
        columns={'Branch': 'ที่ทำการไปรษณีย์', 'Total': 'รวมค้างสะสม'}
    )
    return banner_html, kpis_html, fig_line, fig_bar, grid_df

# CSS สไตล์ Glassmorphism
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap');

* {
    font-family: 'Kanit', sans-serif !important;
}

body, .gradio-container {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important;
    min-height: 100vh;
}

/* หัวข้อระบบ */
.header-box {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.9);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.header-title {
    font-size: 26px;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-sub {
    font-size: 14px;
    color: #64748b;
    margin-top: 6px;
}

/* แผงควบคุมตัวกรอง */
.filter-box {
    background: rgba(255, 255, 255, 0.65);
    backdrop-filter: blur(10px);
    border-radius: 18px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.8);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.03);
    margin-bottom: 16px;
}

/* ป้ายแจ้งเตือน */
.banner-alert {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    border-radius: 16px;
    font-size: 15px;
    margin-bottom: 20px;
    animation: fadeIn 0.4s ease-in-out;
}

.banner-alert.critical {
    background: linear-gradient(135deg, #ff416c, #ff4b2b);
    color: white;
    box-shadow: 0 8px 20px rgba(255, 65, 108, 0.3);
}

.banner-alert.safe {
    background: linear-gradient(135deg, #11998e, #38ef7d);
    color: white;
    box-shadow: 0 8px 20px rgba(56, 239, 125, 0.25);
}

/* KPI Cards */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
}

.kpi-card {
    border-radius: 20px;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: white;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.kpi-card:hover {
    transform: translateY(-3px);
}

.card-red {
    background: linear-gradient(135deg, #ff4757, #ff6b81);
    box-shadow: 0 10px 25px rgba(255, 71, 87, 0.3);
}

.card-amber {
    background: linear-gradient(135deg, #ffa502, #eccc68);
    box-shadow: 0 10px 25px rgba(255, 165, 2, 0.25);
}

.card-purple {
    background: linear-gradient(135deg, #6c5ce7, #a29bfe);
    box-shadow: 0 10px 25px rgba(108, 92, 231, 0.3);
}

.kpi-label {
    font-size: 13px;
    font-weight: 500;
    opacity: 0.9;
    display: block;
}

.kpi-value {
    font-size: 28px;
    font-weight: 700;
    display: block;
    margin-top: 4px;
}

.kpi-value small {
    font-size: 14px;
    font-weight: 400;
}

.kpi-icon {
    font-size: 34px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 14px;
    width: 52px;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* ปรับแต่งตาราง */
.dataframe-wrap {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    background: rgba(255, 255, 255, 0.75) !important;
}
"""

region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

with gr.Blocks(title="SLA Risk Dashboard ปข.3", css=custom_css) as demo:
    # ส่วนหัว Header
    gr.HTML("""
    <div class="header-box">
        <h1 class="header-title">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA สลากกินแบ่งรัฐบาล</h1>
        <div class="header-sub">สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า</div>
    </div>
    """)

    # แผงตัวกรองข้อมูล
    with gr.Row(elem_classes=["filter-box"]):
        time_filter = gr.Dropdown(
            choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90)],
            value=7, label="🕒 เลือกช่วงเวลา"
        )
        region_filter = gr.Dropdown(choices=region_list, value="ALL", label="🏢 กลุ่ม ปจ.")
        branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="📍 ชื่อที่ทำการ")
        refresh_btn = gr.Button("🔍 ประมวลผลและวิเคราะห์", variant="primary")

    # แบนเนอร์แจ้งเตือน AI
    alert_box = gr.HTML()

    # การ์ดแสดง KPIs
    kpi_box = gr.HTML()

    # กราฟเปรียบเทียบ
    with gr.Row():
        chart_line = gr.Plot(label="แนวโน้มการค้างจ่าย")
        chart_bar = gr.Plot(label="Top 5 สาขาตกค้างสูงสุด")

    # ตารางรายงานสรุป
    gr.HTML("<h3 style='margin: 15px 0 5px 0; color:#1e293b;'>📋 รายละเอียดข้อมูลการตกค้างรายที่ทำการ</h3>")
    table_grid = gr.Dataframe(interactive=False, elem_classes=["dataframe-wrap"])

    inputs = [time_filter, region_filter, branch_filter]
    outputs = [alert_box, kpi_box, chart_line, chart_bar, table_grid]

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
