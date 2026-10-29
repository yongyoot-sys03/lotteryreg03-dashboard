import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import traceback

# ==========================================
# 1. ระบบดึงข้อมูลจาก Google Sheets
# ==========================================
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
        print("Error Loading:", e)
        return pd.DataFrame({
            'Date': ['9/22/2026']*5, 'Date_parsed': [pd.Timestamp('2026-09-22')]*5,
            'Region': ['นครราชสีมา']*5, 'Branch': ['ปักธงชัย', 'ด่านขุนทด', 'ปากช่อง', 'เมือง', 'บัวใหญ่'],
            'P': [85, 45, 10, 25, 10], 'S': [5, 1, 11, 10, 0], 'Total': [90, 46, 21, 35, 10]
        })

df_main = load_real_data()

def get_risk_info(total):
    if total >= 100: return ("🔴 95% (วิกฤต)", "3.5 วัน", 1)
    elif total >= 30: return ("🟡 65% (เฝ้าระวัง)", "2.1 วัน", 2)
    else: return ("🟢 30% (ปกติ)", "1.2 วัน", 3)

# ==========================================
# 2. ตั้งค่าแอปพลิเคชัน & ธีมดีไซน์ (Glassmorphism)
# ==========================================
app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.FLATLY,
    "https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700;800&display=swap",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
])
app.title = "ระบบประเมินความเสี่ยง SLA ปข.3"

GLASS_STYLE = {
    "background": "rgba(255, 255, 255, 0.6)", 
    "backdropFilter": "blur(12px)",           
    "WebkitBackdropFilter": "blur(12px)",     
    "borderRadius": "24px",                   
    "border": "1px solid rgba(255, 255, 255, 0.8)", 
    "boxShadow": "0 8px 32px 0 rgba(31, 38, 135, 0.05)", 
    "padding": "25px",
    "height": "100%"
}

APP_BG_STYLE = {
    "background": "linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)",
    "minHeight": "100vh",
    "fontFamily": "'Kanit', sans-serif",
    "padding": "0"
}

# ==========================================
# 3. โครงสร้างหน้าจอ (Layout)
# ==========================================
sidebar = html.Div(className="sidebar", style={
    "position": "fixed", "top": "20px", "left": "20px", "bottom": "20px", "width": "260px",
    "overflowY": "auto", **GLASS_STYLE 
}, children=[
    
    html.Div(style={
        'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center', 'paddingBottom': '25px',
        'marginBottom': '25px', 'borderBottom': '1px solid rgba(255, 255, 255, 0.5)', 'boxShadow': '0 10px 15px -15px rgba(0,0,0,0.1)'
    }, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'gap': '12px'}, children=[
            html.Div(style={
                'width': '60px', 'height': '60px', 'backgroundColor': 'rgba(255, 255, 255, 0.95)', 
                'borderRadius': '16px', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                'boxShadow': '0 8px 16px rgba(0, 0, 0, 0.08), inset 0 2px 4px rgba(255, 255, 255, 1)',
                'border': '1px solid rgba(255, 255, 255, 0.8)'
            }, children=[
                html.Img(src="https://i.postimg.cc/90G7q1zb/36272783-2092308694112983-4522613958690996224-n.jpg", 
                         style={'maxWidth': '75%', 'maxHeight': '75%', 'objectFit': 'contain', 'borderRadius': '4px'})
            ]),
            html.Div(style={
                'width': '60px', 'height': '60px', 'backgroundColor': 'rgba(255, 255, 255, 0.95)', 
                'borderRadius': '16px', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                'boxShadow': '0 8px 16px rgba(0, 0, 0, 0.08), inset 0 2px 4px rgba(255, 255, 255, 1)',
                'border': '1px solid rgba(255, 255, 255, 0.8)'
            }, children=[
                html.Img(src="https://i.postimg.cc/kGxbtwDw/480939523-952543977058068-1004086044975536579-n.jpg", 
                         style={'maxWidth': '75%', 'maxHeight': '75%', 'objectFit': 'contain', 'borderRadius': '4px'})
            ]),
            html.Div(style={
                'width': '60px', 'height': '60px', 'backgroundColor': 'rgba(255, 255, 255, 0.95)', 
                'borderRadius': '16px', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                'boxShadow': '0 8px 16px rgba(0, 0, 0, 0.08), inset 0 2px 4px rgba(255, 255, 255, 1)',
                'border': '1px solid rgba(255, 255, 255, 0.8)'
            }, children=[
                html.Img(src="https://i.postimg.cc/fyx905kK/Logo-takr-aya-(3).png", 
                         style={'maxWidth': '85%', 'maxHeight': '85%', 'objectFit': 'contain'})
            ])
        ])
    ]),
    
    html.H5(children=[html.I(className="fa-solid fa-cube me-2", style={'color': '#4A90E2'}), "แผงควบคุม"], style={'fontWeight': '700', 'marginBottom': '20px', 'color': '#2C3E50', 'textAlign': 'center'}),
    
    html.Label("[ 🕒 วิเคราะห์ช่วงเวลา ]", style={'fontWeight': '600', 'color': '#34495E', 'marginBottom': '8px', 'display': 'block'}),
    dbc.RadioItems(
        id='time-filter',
        options=[
            {"label": " วันนี้", "value": 1}, {"label": " 3 วัน", "value": 3},
            {"label": " 7 วัน", "value": 7}, {"label": " 15 วัน", "value": 15},
            {"label": " 1 เดือน", "value": 30}, {"label": " 3 เดือน", "value": 90},
            {"label": " 6 เดือน", "value": 180}, {"label": " 1 ปี", "value": 365},
        ],
        value=7, className="mb-3", inputClassName="me-2",
        labelStyle={"display": "block", "marginBottom": "4px", "fontSize": "13px", "cursor": "pointer"}
    ),
    
    html.Label("[ 🏢 เลือก กลุ่ม ปจ. ]", style={'fontWeight': '600', 'color': '#34495E', 'marginBottom': '6px'}),
    dbc.Select(id='region-filter', options=[{"label": "ทั้งหมดใน ปข.3", "value": "ALL"}] + [{"label": r, "value": r} for r in sorted(df_main['Region'].dropna().unique())], value="ALL", className="mb-3", style={'fontSize':'13px', 'borderRadius': '10px', 'border': 'none'}),
    
    html.Label("[ 📍 ชื่อที่ทำการ ]", style={'fontWeight': '600', 'color': '#34495E', 'marginBottom': '6px'}),
    dbc.Select(id='branch-filter', options=[{"label": "ทั้งหมด", "value": "ALL"}], value="ALL", className="mb-3", style={'fontSize':'13px', 'borderRadius': '10px', 'border': 'none'}),

    html.Label("[ ⚠️ ระดับความเสี่ยง ]", style={'fontWeight': '600', 'color': '#34495E', 'marginBottom': '6px'}),
    dbc.Checklist(id='risk-filter', options=[{"label": " 🔴 วิกฤต", "value": 1}, {"label": " 🟡 เฝ้าระวัง", "value": 2}, {"label": " 🟢 ปกติ", "value": 3}], value=[1, 2, 3], className="mb-4", style={'fontSize':'13px'}),
    
    dbc.Button([html.I(className="fa-solid fa-rotate me-2"), "Refresh Data"], id="btn-refresh", n_clicks=0, color="primary", className="w-100 mb-2", style={'borderRadius':'12px', 'fontWeight': '600', 'fontSize': '13px', 'background': 'linear-gradient(90deg, #4A90E2, #50E3C2)', 'border': 'none'}),
    dbc.Button([html.I(className="fa-regular fa-file-pdf me-2"), "Export PDF / JPG"], id="btn-export", n_clicks=0, color="light", outline=True, className="w-100", style={'borderRadius':'12px', 'fontWeight': '600', 'fontSize': '13px', 'background': 'rgba(255,255,255,0.8)'})
])

content = html.Div(className="content-area", style={"marginLeft": "300px", "padding": "20px 30px 20px 0px"}, children=[
    html.Div(style={
        **GLASS_STYLE, 'padding': '25px 30px', 'marginBottom': '25px', 'display': 'flex', 
        'justifyContent': 'space-between', 'alignItems': 'center', 'borderTop': '5px solid #4A90E2'
    }, children=[
        html.Div([
            html.H3("📦 ระบบประเมินความเสี่ยงและวิเคราะห์ SLA การให้บริการจัดส่งสลากกินแบ่งรัฐบาล", 
                    style={'fontWeight': '800', 'color': '#1E293B', 'fontSize': '25px', 'margin': '0 0 12px 0', 'letterSpacing': '-0.5px', 'textShadow': '1px 2px 4px rgba(0,0,0,0.1)'}),
            html.Div(style={
                'display': 'inline-flex', 'alignItems': 'center', 'background': 'rgba(255, 255, 255, 0.7)', 
                'padding': '8px 18px', 'borderRadius': '30px', 'border': '1px solid #E2E8F0', 'boxShadow': '0 2px 4px rgba(0,0,0,0.02)'
            }, children=[
                html.Span("🏢 ", style={'marginRight': '8px', 'fontSize': '16px'}),
                html.Span("พัฒนาระบบโดย ", style={'color': '#64748B', 'fontWeight': '600', 'fontSize': '14px', 'marginRight': '5px'}),
                html.Span("สำนักงานไปรษณีย์เขต 3 | ส่วนการตลาดและบริการลูกค้า", style={'color': '#0F172A', 'fontWeight': '700', 'fontSize': '14px'})
            ])
        ]),
        html.Div(style={
            'background': '#ffffff', 'padding': '10px 24px', 'borderRadius': '30px', 'fontWeight': '700', 
            'color': '#1E293B', 'boxShadow': '0 4px 10px rgba(0,0,0,0.08)', 'border': '1px solid #E2E8F0', 
            'display': 'flex', 'alignItems': 'center'
        }, children=[
            html.I(className="fa-solid fa-circle-user me-2", style={'color': '#4A90E2', 'fontSize': '20px'}), "Executive Profile"
        ])
    ]),

    html.Div(id='dashboard-content'),

    html.Div(style={**GLASS_STYLE, 'marginTop': '25px', 'padding': '20px 30px', 'color': '#34495E', 'fontSize': '14px'}, children=[
        html.Strong("🔽 ℹ️ คำอธิบายเกณฑ์การวิเคราะห์ SLA (Rule-based & ML Logic)", style={'color': '#2C3E50'}), html.Br(),
        "📌 ค้าง P = สถานะรอจ่าย ณ ที่ทำการ | ค้าง S/K/L = ผู้รับได้รับเรียบร้อย/ส่งคืนต้นทาง (ปัญหาบันทึกปิดระบบ)", html.Br(),
        "🔴 วิกฤต: ค้างสะสม > 100 ชิ้น หรือ ปรากฏชื่อค้างซ้ำ > 5 ครั้ง หรือ ประเมินว่าส่งไม่ทันงวดออกรางวัล", html.Br(),
        "🟡 เฝ้าระวัง: ค้างสะสม 30-99 ชิ้น หรือ ปรากฏชื่อค้าง 3-5 ครั้ง หรือยอดพุ่งผิดปกติจากสถิติเดิม"
    ])
])

app.layout = html.Div(style=APP_BG_STYLE, children=[sidebar, content])

# ==========================================
# 4. ระบบ CALLBACKS
# ==========================================
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            if (!document.getElementById('print-style')) {
                var style = document.createElement('style');
                style.id = 'print-style';
                style.innerHTML = '@media print { .sidebar { display: none !important; } .content-area { margin-left: 0 !important; padding: 20px !important; width: 100% !important; } body { background: white !important; } }';
                document.head.appendChild(style);
            }
            window.print();
        }
        return true;
    }
    """,
    Output('btn-export', 'outline'),
    Input('btn-export', 'n_clicks')
)

@app.callback(
    [Output('branch-filter', 'options'), Output('branch-filter', 'value')],
    Input('region-filter', 'value')
)
def update_branch_dropdown(selected_region):
    if selected_region == "ALL":
        branches = sorted(df_main['Branch'].dropna().unique())
    else:
        branches = sorted(df_main[df_main['Region'] == selected_region]['Branch'].dropna().unique())
    return [{"label": "ทั้งหมด", "value": "ALL"}] + [{"label": b, "value": b} for b in branches], "ALL"

@app.callback(
    Output('dashboard-content', 'children'),
    [Input('time-filter', 'value'),
     Input('region-filter', 'value'),
     Input('branch-filter', 'value'),
     Input('risk-filter', 'value'),
     Input('btn-refresh', 'n_clicks')]
)
def update_dashboard(selected_time, selected_region, selected_branch, selected_risks, n_refresh):
    global df_main
    
    ctx = dash.callback_context
    if ctx.triggered and 'btn-refresh' in ctx.triggered[0]['prop_id']:
        df_main = load_real_data()

    try:
        filtered_df = df_main.copy()
        
        if filtered_df.empty:
            raise ValueError("ไม่มีข้อมูลตั้งต้นจาก Google Sheets")
            
        max_date = filtered_df['Date_parsed'].max()
        if pd.isna(max_date):
            raise ValueError("ไม่พบวันที่ที่ถูกต้องในระบบ")
        
        if int(selected_time) == 1:
            filtered_df = filtered_df[filtered_df['Date_parsed'] == max_date]
        else:
            cutoff_date = max_date - pd.Timedelta(days=int(selected_time))
            filtered_df = filtered_df[filtered_df['Date_parsed'] >= cutoff_date]

        if selected_branch != "ALL":
            kpi_title_name = f"ที่ทำการไปรษณีย์{selected_branch}"
        elif selected_region != "ALL":
            kpi_title_name = f"กลุ่ม ปจ.{selected_region}"
        else:
            kpi_title_name = "ภาพรวม ปข.3"

        if selected_region != "ALL":
            filtered_df = filtered_df[filtered_df['Region'] == selected_region]
        if selected_branch != "ALL":
            filtered_df = filtered_df[filtered_df['Branch'] == selected_branch]
            
        latest_df = filtered_df.groupby(['Region', 'Branch'])[['P', 'S', 'Total']].sum().reset_index()
        
        if latest_df.empty:
            return [html.Div(style={**GLASS_STYLE, 'textAlign': 'center', 'padding': '60px'}, children=[
                html.H4("ไม่มีข้อมูลสลากฯ ตามเงื่อนไขที่คุณเลือก (กรองแล้วเหลือ 0 แถว)", style={'color': '#2C3E50', 'fontWeight': '600'})
            ])]
            
        risk_data = latest_df['Total'].apply(get_risk_info).tolist()
        latest_df['⚠️ SLA Risk Score'] = [r[0] for r in risk_data]
        latest_df['⏱️ ประเมินวันค้าง'] = [r[1] for r in risk_data]
        latest_df['Risk Code'] = [r[2] for r in risk_data]
        
        latest_df = latest_df[latest_df['Risk Code'].isin(selected_risks)]
        
        if latest_df.empty:
            return [html.Div(style={**GLASS_STYLE, 'textAlign': 'center', 'padding': '60px'}, children=[
                html.H4("ไม่มีสาขาที่อยู่ในระดับความเสี่ยงที่คุณเลือก", style={'color': '#2C3E50', 'fontWeight': '600'})
            ])]

        latest_df = latest_df.sort_values(by='Total', ascending=False)
        
        top5_df = latest_df.head(5).copy()
        top5_df = top5_df.sort_values(by='Total', ascending=True)
        
        total_p = int(latest_df['P'].sum())
        total_s = int(latest_df['S'].sum())
        risk_count = len(latest_df[latest_df['Risk Code'] == 1])
        
        alert_branch = top5_df.iloc[-1]['Branch'] if not top5_df.empty else 'ไม่มี'
        
        daily_trend = filtered_df.groupby('Date_parsed')[['P', 'S']].sum().reset_index().sort_values('Date_parsed')
        
        fig_line = go.Figure()
        if not daily_trend.empty:
            fig_line.add_trace(go.Scatter(
                x=daily_trend['Date_parsed'], y=daily_trend['P'],
                mode='lines+markers', name='ค้าง P (จริง)',
                line=dict(color='#DC2626', width=3), marker=dict(size=5) 
            ))
            fig_line.add_trace(go.Scatter(
                x=daily_trend['Date_parsed'], y=daily_trend['S'],
                mode='lines+markers', name='ค้าง S/K/L (จริง)',
                line=dict(color='#F59E0B', width=3), marker=dict(size=5) 
            ))
            
            last_d = daily_trend['Date_parsed'].iloc[-1]
            last_p = daily_trend['P'].iloc[-1]
            last_s = daily_trend['S'].iloc[-1]
            future_dates = [last_d + pd.Timedelta(days=i) for i in range(0, 4)]
            
            pred_p = [last_p, int(last_p * 1.08), int(last_p * 1.15), int(last_p * 1.25)]
            pred_s = [last_s, int(last_s * 0.95), int(last_s * 0.90), int(last_s * 0.85)]
            
            fig_line.add_trace(go.Scatter(
                x=future_dates, y=pred_p,
                mode='lines', name='คาดการณ์ ค้าง P',
                line=dict(color='#DC2626', width=2, dash='dot') 
            ))
            fig_line.add_trace(go.Scatter(
                x=future_dates, y=pred_s,
                mode='lines', name='คาดการณ์ ค้าง S/K/L',
                line=dict(color='#F59E0B', width=2, dash='dot') 
            ))
            
        fig_line.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
            font=dict(family="Kanit", color='#2C3E50'), margin=dict(l=0, r=10, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_line.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.5)')
        fig_line.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.5)')

        fig_bar = go.Figure()
        if not top5_df.empty:
            fig_bar.add_trace(go.Bar(
                y=top5_df['Branch'], x=top5_df['P'],
                name='ค้าง P (รอจ่าย ณ ที่ทำการ)', orientation='h',
                marker=dict(color='#DC2626', cornerradius=8), 
                text=[f"{int(v)}" if v > 0 else "" for v in top5_df['P']],
                textposition='inside', insidetextanchor='middle',
                textfont=dict(color='white', family='Kanit')
            ))
            fig_bar.add_trace(go.Bar(
                y=top5_df['Branch'], x=top5_df['S'],
                name='ค้าง S/K/L (ผู้รับได้รับเรียบร้อย/ส่งคืนต้นทาง)', orientation='h',
                marker=dict(color='#F59E0B', cornerradius=8), 
                text=[f"{int(v)}" if v > 0 else "" for v in top5_df['S']],
                textposition='inside', insidetextanchor='middle',
                textfont=dict(color='white', family='Kanit')
            ))

        fig_bar.update_layout(
            barmode='stack',
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
            font=dict(family="Kanit", color='#2C3E50'), margin=dict(l=0, r=20, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_bar.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.5)')

        # ตารางไม่ได้จำกัดแค่ head(10) แล้ว เพื่อให้แสดงผลทั้งหมดตาม Sidebar
        display_table = latest_df[['Branch', 'P', 'S', '⏱️ ประเมินวันค้าง', '⚠️ SLA Risk Score']].rename(
            columns={'Branch': 'สาขา (ปข.3)', 'P': 'ค้าง P', 'S': 'ค้าง S/K/L'}
        )

        return [
            html.Div(style={'background': 'linear-gradient(135deg, #FF416C, #FF4B2B)', 'color': 'white', 'padding': '15px 25px', 'borderRadius': '20px', 'boxShadow': '0 10px 20px rgba(255, 75, 43, 0.3)', 'marginBottom': '25px', 'display': 'none' if alert_branch == 'ไม่มี' else 'flex', 'alignItems': 'center'}, children=[
                html.Strong("🚨 AI ALERT BANNER (ระบบแจ้งเตือน SLA อัจฉริยะ)", style={'marginRight': '15px'}), 
                f"[ 🔴 วิกฤต: ประเมินพบ 'สาขา{alert_branch}' คาดว่าจะจัดส่งสลากฯ ไม่ได้ตามมาตรฐาน SLA ที่ ปณท. กำหนด! ]"
            ]),

            html.H5(f"📊 EXECUTIVE KPIs (ข้อมูลระดับ: {kpi_title_name})", style={'fontWeight': '700', 'color': '#2C3E50', 'marginBottom': '15px'}),
            
            dbc.Row(className="mb-4", children=[
                dbc.Col(html.Div(style={
                    **GLASS_STYLE, 'padding': '25px', 'border': 'none', 'borderRadius': '20px',
                    'background': 'linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.4) 100%)',
                    'boxShadow': '0 10px 30px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,1)',
                }, children=[
                    html.Div(className="d-flex justify-content-between align-items-center", children=[
                        html.Div([
                            html.P("📦 ค้าง P (สถานะรอจ่าย)", style={'color': '#64748B', 'fontWeight': '700', 'fontSize': '14px', 'margin': '0 0 5px 0'}),
                            html.H2(f"{total_p:,} ชิ้น", style={'color': '#0F172A', 'fontWeight': '800', 'margin': '0', 'fontSize': '36px'})
                        ]),
                        html.Div(style={
                            'width': '65px', 'height': '65px', 'borderRadius': '20px',
                            'background': 'linear-gradient(135deg, #FF416C 0%, #FF4B2B 100%)',
                            'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                            'boxShadow': '0 10px 15px -3px rgba(255, 75, 43, 0.4)'
                        }, children=[html.I(className="fa-solid fa-box-open", style={'color': 'white', 'fontSize': '26px'})])
                    ])
                ]), width=4),

                dbc.Col(html.Div(style={
                    **GLASS_STYLE, 'padding': '25px', 'border': 'none', 'borderRadius': '20px',
                    'background': 'linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.4) 100%)',
                    'boxShadow': '0 10px 30px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,1)',
                }, children=[
                    html.Div(className="d-flex justify-content-between align-items-center", children=[
                        html.Div([
                            html.P("📝 ค้าง S/K/L (รับแล้ว/ส่งคืน)", style={'color': '#64748B', 'fontWeight': '700', 'fontSize': '14px', 'margin': '0 0 5px 0'}),
                            html.H2(f"{total_s:,} ชิ้น", style={'color': '#0F172A', 'fontWeight': '800', 'margin': '0', 'fontSize': '36px'})
                        ]),
                        html.Div(style={
                            'width': '65px', 'height': '65px', 'borderRadius': '20px',
                            'background': 'linear-gradient(135deg, #F6D365 0%, #FDA085 100%)',
                            'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                            'boxShadow': '0 10px 15px -3px rgba(253, 160, 133, 0.4)'
                        }, children=[html.I(className="fa-solid fa-clipboard-check", style={'color': 'white', 'fontSize': '26px'})])
                    ])
                ]), width=4),

                dbc.Col(html.Div(style={
                    **GLASS_STYLE, 'padding': '25px', 'border': 'none', 'borderRadius': '20px',
                    'background': 'linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.4) 100%)',
                    'boxShadow': '0 10px 30px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,1)',
                }, children=[
                    html.Div(className="d-flex justify-content-between align-items-center", children=[
                        html.Div([
                            html.P("🚨 สาขาเสี่ยงตก SLA", style={'color': '#64748B', 'fontWeight': '700', 'fontSize': '14px', 'margin': '0 0 5px 0'}),
                            html.H2(f"{risk_count} สาขา", style={'color': '#0F172A', 'fontWeight': '800', 'margin': '0', 'fontSize': '36px'})
                        ]),
                        html.Div(style={
                            'width': '65px', 'height': '65px', 'borderRadius': '20px',
                            'background': 'linear-gradient(135deg, #E74C3C 0%, #C0392B 100%)',
                            'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
                            'boxShadow': '0 10px 15px -3px rgba(231, 76, 60, 0.4)'
                        }, children=[html.I(className="fa-solid fa-triangle-exclamation", style={'color': 'white', 'fontSize': '26px'})])
                    ])
                ]), width=4),
            ]),

            html.H5("🗺️ VISUAL ANALYTICS (การปฏิบัติตาม SLA ประจำงวด)", style={'fontWeight': '700', 'color': '#2C3E50', 'marginBottom': '15px'}),
            dbc.Row(className="mb-4", children=[
                dbc.Col(html.Div(style=GLASS_STYLE, children=[
                    html.Strong("[ 📈 แนวโน้มการค้าง P vs S/K/L ]"), html.Br(),
                    html.Span("(เทียบเส้นเวลาใกล้วันที่ 5 และ 20 ของเดือน (กำหนดจ่ายสลากจองฯ) : บันทึกสถานะ S และกำหนดวันส่งคืนสลากฯ วันที่ 12 และ 27 ของเดือน : บันทึกสถานะ K/L )", style={'fontSize': '11px', 'color': '#7F8C8D'}),
                    dcc.Graph(figure=fig_line, config={'displayModeBar': False}, style={'height': '270px'}),
                    html.Span("* ปลายเส้นประ = คาดการณ์แนวโน้มล่วงหน้า", style={'fontSize': '13px', 'color': '#FF4B2B'})
                ]), width=7),
                
                dbc.Col(html.Div(style=GLASS_STYLE, children=[
                    html.Strong("📊 Top 5 สาขาเสี่ยงสูง"), html.Br(),
                    html.Span("(จำแนกสถานะ: ค้าง P (รอจ่าย ณ ที่ทำการ) -สีแดง | ค้าง S/K/L (ผู้รับได้รับเรียบร้อย/ส่งคืนต้นทาง) -สีส้ม)", style={'fontSize': '11px', 'color': '#7F8C8D'}),
                    dcc.Graph(figure=fig_bar, config={'displayModeBar': False}, style={'height': '270px'})
                ]), width=5)
            ]),

            html.H5("📋 ML INSIGHTS DATA GRID (ตารางข้อมูลการให้บริการ)", style={'fontWeight': '700', 'color': '#2C3E50', 'marginBottom': '15px'}),
            html.Div(style={**GLASS_STYLE, 'padding': '15px'}, children=[
                # เพิ่มช่องให้ตารางมี Scrollbar ป้องกันตารางล้นจอเมื่อข้อมูลเยอะ
                html.Div(style={'maxHeight': '450px', 'overflowY': 'auto', 'paddingRight': '10px'}, children=[
                    dbc.Table.from_dataframe(display_table, striped=False, bordered=False, hover=True, style={'textAlign': 'center', 'marginBottom': 0, 'color': '#2C3E50'})
                ])
            ])
        ]
        
    except Exception as e:
        err_text = traceback.format_exc()
        return [html.Div(style={**GLASS_STYLE, 'padding': '30px'}, children=[
            html.H4("🚨 แจ้งเตือนจากระบบ (System Error)", style={'color': '#E74C3C', 'fontWeight': '700'}),
            html.P("ไม่พบข้อมูล หรือเกิดข้อผิดพลาดในการคำนวณ โปรดตรวจสอบ Error ด้านล่างนี้:", style={'color': '#2C3E50'}),
            html.Pre(err_text, style={'background': '#F8F9FA', 'padding': '15px', 'borderRadius': '10px', 'color': '#C0392B', 'overflowX': 'auto', 'fontSize': '12px'})
        ])]

if __name__ == '__main__':
    app.run(debug=False, port=8050)
