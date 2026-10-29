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
    if total >= 100: return ("🔴 วิกฤต", "3.5 วัน", 1)
    elif total >= 30: return ("🟡 เฝ้าระวัง", "2.1 วัน", 2)
    else: return ("🟢 ปกติ", "1.2 วัน", 3)

df_base = load_real_data()

@spaces.GPU
def update_dashboard(selected_time_days, selected_region, selected_branch):
    df = load_real_data() if df_base.empty else df_base.copy()
    if df.empty:
        empty_banner = "<div class='alert-pill alert-safe'>⚠️ ไม่พบการเชื่อมต่อฐานข้อมูล</div>"
        empty_kpi = ""
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
    latest_df['⚠️ สถานะ SLA'] = [r[0] for r in risk_info]
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

    # 1. Alert Banner ทรงโมเดิร์น Pill
    if not top5.empty and top5.iloc[-1]['Total'] >= 100:
        crit_branch = top5.iloc[-1]['Branch']
        crit_qty = int(top5.iloc[-1]['Total'])
        banner_html = f"""
        <div class="alert-pill alert-critical">
            <span class="pulse-beacon"></span>
            <div><b>AI Predictive Alert:</b> ตรวจพบ <u>สาขา{crit_branch}</u> มีปริมาณตกค้างสะสม <b>{crit_qty:,} ชิ้น</b> เสี่ยงเกินกรอบเวลามาตรฐาน SLA ของ ปณท!</div>
        </div>
        """
    else:
        banner_html = """
        <div class="alert-pill alert-safe">
            <span class="safe-beacon"></span>
            <div><b>SLA Performance Normal:</b> ทุกที่ทำการบริหารจัดการการนำจ่ายได้ตามเกณฑ์มาตรฐาน</div>
        </div>
        """

    # 2. Bento KPI Cards พร้อม Badge และ Micro-bar
    kpis_html = f"""
    <div class="bento-kpi-grid">
        <div class="bento-card bento-red">
            <div class="bento-header">
                <span class="bento-title">ค้าง P (รอการนำจ่าย)</span>
                <span class="bento-badge red-badge">{pct_p:.1f}%</span>
            </div>
            <div class="bento-val">{total_p:,} <span class="val-sub">ชิ้น</span></div>
            <div class="bento-bar-bg"><div class="bento-bar-fill bar-red" style="width: {pct_p}%;"></div></div>
            <div class="bento-footnote">สถานะรอจ่าย ณ ที่ทำการ</div>
        </div>

        <div class="bento-card bento-amber">
            <div class="bento-header">
                <span class="bento-title">ค้าง S/K/L (รับแล้ว/ส่งคืน)</span>
                <span class="bento-badge amber-badge">{pct_s:.1f}%</span>
            </div>
            <div class="bento-val">{total_s:,} <span class="val-sub">ชิ้น</span></div>
            <div class="bento-bar-bg"><div class="bento-bar-fill bar-amber" style="width: {pct_s}%;"></div></div>
            <div class="bento-footnote">ส่งคืนศูนย์ฯ / รับฝากต่อ</div>
        </div>

        <div class="bento-card bento-blue">
            <div class="bento-header">
                <span class="bento-title">สาขาวิกฤตเสี่ยงตก SLA</span>
                <span class="bento-badge blue-badge">เร่งด่วน</span>
            </div>
            <div class="bento-val">{risk_branches} <span class="val-sub">สาขา</span></div>
            <div class="bento-bar-bg"><div class="bento-bar-fill bar-blue" style="width: {min(risk_branches*15, 100)}%;"></div></div>
            <div class="bento-footnote">จากทั้งหมด {len(latest_df):,} สาขาที่มีรายการ</div>
        </div>
    </div>
    """

    # 3. Modern Smooth Line Chart
    daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    if not daily_trend.empty:
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['P'],
            mode='lines+markers', name='ค้าง P',
            line=dict(color='#F43F5E', width=3, shape='spline'),
            marker=dict(size=6, color='#F43F5E'),
            fill='tozeroy', fillcolor='rgba(244, 63, 94, 0.05)'
        ))
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['S'],
            mode='lines+markers', name='ค้าง S/K/L',
            line=dict(color='#F59E0B', width=3, shape='spline'),
            marker=dict(size=6, color='#F59E0B'),
            fill='tozeroy', fillcolor='rgba(245, 158, 11, 0.05)'
        ))
    fig_line.update_layout(
        template="plotly_white",
        margin=dict(l=15, r=15, t=20, b=15),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='#F1F5F9', linecolor='#E2E8F0'),
        yaxis=dict(showgrid=True, gridcolor='#F1F5F9', linecolor='#E2E8F0'),
        height=320
    )

    # 4. Modern Stacked Bar Chart
    fig_bar = go.Figure()
    if not top5.empty:
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['P'], name='ค้าง P', orientation='h',
            marker=dict(color='#F43F5E', cornerradius=4),
            text=top5['P'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF")
        ))
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['S'], name='ค้าง S/K/L', orientation='h',
            marker=dict(color='#F59E0B', cornerradius=4),
            text=top5['S'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF")
        ))
    fig_bar.update_layout(
        barmode='stack',
        template="plotly_white",
        margin=dict(l=15, r=15, t=20, b=15),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='#F1F5F9', linecolor='#E2E8F0'),
        yaxis=dict(showgrid=False, linecolor='#E2E8F0'),
        height=320
    )

    grid_df = latest_df[['Branch', 'P', 'S', 'Total', '⏱️ คาดการณ์ค้าง', '⚠️ สถานะ SLA']].rename(
        columns={'Branch': 'ที่ทำการไปรษณีย์', 'Total': 'รวมค้างสะสม (ชิ้น)'}
    )
    return banner_html, kpis_html, fig_line, fig_bar, grid_df

# CSS สไตล์ Clean SaaS Dashboard
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Kanit:wght@300;400;500;600&display=swap');

* {
    font-family: 'Kanit', sans-serif !important;
}

body, .gradio-container {
    background-color: #F8FAFC !important;
    color: #1E293B !important;
}

/* Header */
.modern-header {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.03);
}

.brand-title {
    font-size: 24px;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
}

.brand-sub {
    font-size: 13px;
    color: #64748B;
    margin-top: 4px;
}

.brand-pill {
    background: #EFF6FF;
    color: #2563EB;
    border: 1px solid #BFDBFE;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 9999px;
}

/* Alert Pill */
.alert-pill {
    border-radius: 12px;
    padding: 12px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    border: 1px solid transparent;
}

.alert-critical {
    background: #FFF1F2;
    border-color: #FECDD3;
    color: #9F1239;
}

.alert-safe {
    background: #F0FDF4;
    border-color: #BBF7D0;
    color: #166534;
}

.pulse-beacon {
    width: 10px;
    height: 10px;
    background: #E11D48;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(225, 29, 72, 0.7);
    animation: pulse 1.5s infinite;
}

.safe-beacon {
    width: 10px;
    height: 10px;
    background: #16A34A;
    border-radius: 50%;
}

@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(225, 29, 72, 0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(225, 29, 72, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(225, 29, 72, 0); }
}

/* Bento KPI Cards */
.bento-kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
}

.bento-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 20px 24px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.bento-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
}

.bento-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.bento-title {
    font-size: 13px;
    font-weight: 600;
    color: #64748B;
}

.bento-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 9999px;
}

.red-badge { background: #FFE4E6; color: #E11D48; }
.amber-badge { background: #FEF3C7; color: #D97706; }
.blue-badge { background: #DBEAFE; color: #2563EB; }

.bento-val {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 32px;
    font-weight: 800;
    color: #0F172A;
    margin: 8px 0 10px 0;
}

.val-sub {
    font-size: 14px;
    font-weight: 500;
    color: #94A3B8;
}

.bento-bar-bg {
    width: 100%;
    height: 5px;
    background: #F1F5F9;
    border-radius: 9999px;
    overflow: hidden;
    margin-bottom: 8px;
}

.bento-bar-fill {
    height: 100%;
    border-radius: 9999px;
}

.bar-red { background: #F43F5E; }
.bar-amber { background: #F59E0B; }
.bar-blue { background: #2563EB; }

.bento-footnote {
    font-size: 12px;
    color: #94A3B8;
}

/* Card Sections */
.chart-card-box {
    background: #FFFFFF !important;
    border-radius: 16px !important;
    border: 1px solid #E2E8F0 !important;
    padding: 16px !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02) !important;
}

button.primary-btn {
    background: #0284C7 !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 10px rgba(2, 132, 199, 0.25) !important;
}
"""

region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

with gr.Blocks(title="ระบบประเมินความเสี่ยง SLA ปข.3", css=custom_css) as demo:
    # Top Header
    gr.HTML("""
    <div class="modern-header">
        <div>
            <h1 class="brand-title">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA สลากกินแบ่งรัฐบาล</h1>
            <div class="brand-sub">สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า</div>
        </div>
        <div class="brand-pill">ปข.3 EXECUTIVE SUITE</div>
    </div>
    """)

    # Filter Bar
    with gr.Row(elem_classes=["chart-card-box"]):
        time_filter = gr.Dropdown(
            choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90)],
            value=7, label="ช่วงเวลาวิเคราะห์", scale=1
        )
        region_filter = gr.Dropdown(choices=region_list, value="ALL", label="กลุ่ม ปจ.", scale=1)
        branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="ชื่อที่ทำการ", scale=1)
        refresh_btn = gr.Button("⚡ ประมวลผลข้อมูล", variant="primary", elem_classes=["primary-btn"], scale=1)

    # Dynamic Alert
    alert_box = gr.HTML()

    # Bento KPI Grid
    kpi_box = gr.HTML()

    # Analytics Charts
    with gr.Row():
        with gr.Column(elem_classes=["chart-card-box"]):
            gr.Markdown("#### 📈 แนวโน้มการค้างจ่ายสะสมรายวัน")
            chart_line = gr.Plot()
        with gr.Column(elem_classes=["chart-card-box"]):
            gr.Markdown("#### 📊 5 สาขาสูงสุดที่ต้องเร่งรัด")
            chart_bar = gr.Plot()

    # Detailed Table
    with gr.Column(elem_classes=["chart-card-box"]):
        gr.Markdown("#### 📋 รายละเอียดข้อมูลและสถานะ SLA รายที่ทำการ")
        table_grid = gr.Dataframe(interactive=False)

    inputs = [time_filter, region_filter, branch_filter]
    outputs = [alert_box, kpi_box, chart_line, chart_bar, table_grid]

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
