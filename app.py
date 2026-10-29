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
        return "⚠️ ไม่สามารถโหลดข้อมูลได้", "0 ชิ้น", "0 ชิ้น", "0 สาขา", None, None, pd.DataFrame()

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
    alert_txt = f"🚨 แจ้งเตือน: พบสาขา {top5.iloc[-1]['Branch']} มีปริมาณตกค้างวิกฤต เสี่ยงหลุดเกณฑ์ SLA!" if not top5.empty and top5.iloc[-1]['Total'] >= 100 else "🟢 ทุกสาขาอยู่ในเกณฑ์มาตรฐาน"

    # Line Chart
    daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
    fig_line = go.Figure()
    if not daily_trend.empty:
        fig_line.add_trace(go.Scatter(x=daily_trend['Date_parsed'], y=daily_trend['P'], mode='lines+markers', name='ค้าง P', line=dict(color='#DC2626', width=3)))
        fig_line.add_trace(go.Scatter(x=daily_trend['Date_parsed'], y=daily_trend['S'], mode='lines+markers', name='ค้าง S/K/L', line=dict(color='#F59E0B', width=3)))
        fig_line.update_layout(title="แนวโน้มการค้าง P vs S/K/L", margin=dict(l=10, r=10, t=40, b=10), template="plotly_white")

    # Bar Chart
    fig_bar = go.Figure()
    if not top5.empty:
        fig_bar.add_trace(go.Bar(y=top5['Branch'], x=top5['P'], name='ค้าง P', orientation='h', marker=dict(color='#DC2626')))
        fig_bar.add_trace(go.Bar(y=top5['Branch'], x=top5['S'], name='ค้าง S/K/L', orientation='h', marker=dict(color='#F59E0B')))
        fig_bar.update_layout(barmode='stack', title="Top 5 สาขาเสี่ยงสูง", margin=dict(l=10, r=10, t=40, b=10), template="plotly_white")

    grid_df = latest_df[['Branch', 'P', 'S', '⏱️ วันค้าง', '⚠️ SLA Risk']].rename(columns={'Branch': 'สาขา'})
    return alert_txt, f"{total_p:,} ชิ้น", f"{total_s:,} ชิ้น", f"{risk_branches} สาขา", fig_line, fig_bar, grid_df

region_list = ["ALL"] + (sorted(df_base['Region'].dropna().unique().tolist()) if not df_base.empty else [])
branch_list = ["ALL"] + (sorted(df_base['Branch'].dropna().unique().tolist()) if not df_base.empty else [])

with gr.Blocks(title="SLA Risk Dashboard ปข.3") as demo:
    gr.Markdown("# 📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA สลากกินแบ่งรัฐบาล\n### สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า")
    
    with gr.Row():
        time_filter = gr.Dropdown(choices=[("วันนี้", 1), ("3 วัน", 3), ("7 วัน", 7), ("15 วัน", 15), ("1 เดือน", 30), ("3 เดือน", 90)], value=7, label="ช่วงเวลา")
        region_filter = gr.Dropdown(choices=region_list, value="ALL", label="กลุ่ม ปจ.")
        branch_filter = gr.Dropdown(choices=branch_list, value="ALL", label="ชื่อที่ทำการ")
        refresh_btn = gr.Button("🔄 วิเคราะห์ข้อมูล", variant="primary")

    alert_box = gr.Markdown("🟢 ตรวจสอบสถานะความเสี่ยง...")

    with gr.Row():
        kpi_p = gr.Textbox(label="📦 ค้าง P (รอจ่าย)", interactive=False)
        kpi_s = gr.Textbox(label="📝 ค้าง S/K/L (รับแล้ว/ส่งคืน)", interactive=False)
        kpi_risk = gr.Textbox(label="🚨 สาขาเสี่ยงตก SLA", interactive=False)

    with gr.Row():
        chart_line = gr.Plot(label="แนวโน้มการค้างจ่าย")
        chart_bar = gr.Plot(label="Top 5 สาขาตกค้างสูงสุด")

    gr.Markdown("### 📋 ข้อมูลภาพรวมสาขา")
    table_grid = gr.Dataframe(interactive=False)

    inputs = [time_filter, region_filter, branch_filter]
    outputs = [alert_box, kpi_p, kpi_s, kpi_risk, chart_line, chart_bar, table_grid]

    refresh_btn.click(fn=update_dashboard, inputs=inputs, outputs=outputs)
    demo.load(fn=update_dashboard, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, ssr=False)
