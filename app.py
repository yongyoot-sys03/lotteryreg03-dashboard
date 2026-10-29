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
        empty_banner = "<div style='padding:12px 18px;border-radius:10px;background:#FEF2F2;border:1px solid #F87171;color:#991B1B;'>⚠️ ไม่สามารถดึงข้อมูลได้</div>"
        return empty_banner, "0 ชิ้น", "0 ชิ้น", "0 แห่ง", None, None, pd.DataFrame()

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
    risk_branches = len(latest_df[latest_df['Risk Code'] == 1])

    top5 = latest_df.head(5).sort_values(by='Total', ascending=True)

    # Banner แจ้งเตือนสไตล์ Clean Alert
    if not top5.empty and top5.iloc[-1]['Total'] >= 100:
        crit_branch = top5.iloc[-1]['Branch']
        crit_qty = int(top5.iloc[-1]['Total'])
        banner_html = f"""
        <div style="background:#FFF1F2; border-left:5px solid #E11D48; padding:14px 20px; border-radius:10px; box-shadow:0 2px 6px rgba(0,0,0,0.04); display:flex; align-items:center; gap:12px;">
            <span style="font-size:20px;">🚨</span>
            <div style="color:#9F1239; font-size:15px;">
                <strong>แจ้งเตือนวิกฤต SLA:</strong> ที่ทำการ <b>สาขา{crit_branch}</b> มียอดสลากสะสมตกค้าง <b>{crit_qty:,} ชิ้น</b> เสี่ยงเกินกรอบเวลามาตรฐาน SLA ของ ปณท
            </div>
        </div>
        """
    else:
        banner_html = """
        <div style="background:#F0FDF4; border-left:5px solid #16A34A; padding:14px 20px; border-radius:10px; box-shadow:0 2px 6px rgba(0,0,0,0.04); display:flex; align-items:center; gap:12px;">
            <span style="font-size:20px;">✅</span>
            <div style="color:#166534; font-size:15px;">
                <strong>สถานะปกติ:</strong> ปริมาณการนำจ่ายและส่งคืนทุกที่ทำการอยู่ในเกณฑ์ควบคุมมาตรฐาน
            </div>
        </div>
        """

    # Line Chart สไตล์ Enterprise
    daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    if not daily_trend.empty:
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['P'],
            mode='lines+markers', name='ค้าง P (รอจ่าย)',
            line=dict(color='#E11D48', width=3),
            marker=dict(size=7)
        ))
        fig_line.add_trace(go.Scatter(
            x=daily_trend['Date_parsed'], y=daily_trend['S'],
            mode='lines+markers', name='ค้าง S/K/L',
            line=dict(color='#F59E0B', width=3),
            marker=dict(size=7)
        ))
    fig_line.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="", showgrid=True, gridcolor='#F1F5F9'),
        yaxis=dict(title="จำนวน (ชิ้น)", showgrid=True, gridcolor='#F1F5F9'),
        height=320
    )

    # Bar Chart สไตล์ Enterprise
    fig_bar = go.Figure()
    if not top5.empty:
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['P'], name='ค้าง P', orientation='h',
            marker=dict(color='#E11D48'),
            text=top5['P'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF")
        ))
        fig_bar.add_trace(go.Bar(
            y=top5['Branch'], x=top5['S'], name='ค้าง S/K/L', orientation='h',
            marker=dict(color='#F59E0B'),
            text=top5['S'].apply(lambda x: f"{int(x):,}" if x > 0 else ""),
            textposition='inside', insidetextanchor='middle', textfont=dict(color="#FFFFFF")
        ))
    fig_bar.update_layout(
        barmode='stack',
        template="plotly_white",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="รวมค้างสะสม (ชิ้น)", showgrid=True, gridcolor='#F1F5F9'),
        yaxis=dict(title=""),
        height=320
    )

    grid_df = latest_df[['Branch', 'P', 'S', 'Total', '⏱️ คาดการณ์ค้าง', '⚠️ สถานะ SLA']].rename(
        columns={'Branch': 'ที่ทำการไปรษณีย์', 'Total': 'รวมค้างสะสม (ชิ้น)'}
    )
    return banner_html, f"{total_p:,} ชิ้น", f"{total_s:,} ชิ้น", f"{risk_branches} แห่ง", fig_line, fig_bar, grid_df

# ดึงรายการตัวเลือก
region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

# ธีมหลักมาตรฐาน Gradio: Soft Slate
theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="slate",
    font=[gr.themes.GoogleFont("Kanit"), "sans-serif"]
)

with gr.Blocks(title="ระบบประเมินความเสี่ยง SLA ปข.3", theme=theme) as demo:
    # Header ส่วนหัว
    gr.HTML("""
    <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); color:white; padding:22px 28px; border-radius:14px; margin-bottom:16px; box-shadow:0 4px 12px rgba(15,23,42,0.15);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h2 style="margin:0; font-size:24px; font-weight:700; color:#FFFFFF;">📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA สลากกินแบ่งรัฐบาล</h2>
                <div style="color:#94A3B8; font-size:14px; margin-top:4px;">สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า</div>
            </div>
            <div style="background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); padding:6px 14px; border-radius:20px; font-size:12px; font-weight:600; color:#38BDF8;">
                ปข.3 MONITORING
            </div>
        </div>
    </div>
    """)

    # แผงตัวกรองข้อมูล
    with gr.Row():
        time_filter = gr.Dropdown(
            choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90)],
            value=7, label="ช่วงเวลาวิเคราะห์", scale=1
        )
        region_filter = gr.Dropdown(choices=region_list, value="ALL", label="กลุ่ม ปจ.", scale=1)
        branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="ชื่อที่ทำการ", scale=1)
        refresh_btn = gr.Button("🔍 ประมวลผลข้อมูล", variant="primary", scale=1)

    # แถบแจ้งเตือนสถานะ
    alert_box = gr.HTML()

    # ตัวชี้วัดสำคัญ (Executive KPIs)
    with gr.Row():
        kpi_p = gr.Textbox(label="📦 ค้าง P (รอการนำจ่าย)", interactive=False)
        kpi_s = gr.Textbox(label="📝 ค้าง S/K/L (รับแล้ว/ส่งคืน)", interactive=False)
        kpi_risk = gr.Textbox(label="🚨 สาขาวิกฤตเสี่ยงตก SLA", interactive=False)

    # พื้นที่กราฟวิเคราะห์
    with gr.Row():
        chart_line = gr.Plot(label="แนวโน้มการค้างจ่ายรายวัน")
        chart_bar = gr.Plot(label="5 อันดับสาขาสูงสุดที่ต้องเร่งรัด")

    # ตารางรายละเอียด
    gr.Markdown("### 📋 ข้อมูลภาพรวมและระดับความเสี่ยงรายที่ทำการ")
    table_grid = gr.Dataframe(interactive=False)

    inputs = [time_filter, region_filter, branch_filter]
    outputs = [alert_box, kpi_p, kpi_s, kpi_risk, chart_line, chart_bar, table_grid]

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
