import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime, date
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------------------------
st.set_page_config(page_title="Análisis BVC - Terminal Cuantitativo", layout="wide")

# ESTILOS CSS PERSONALIZADOS DE ALTA GAMA (FANCY UI / UX REDISEÑADO)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    .stApp {
        background: radial-gradient(circle at 50% 0%, #0f172a 0%, #030712 100%);
        color: #f3f4f6;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #080d19 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 1.5rem;
    }

    div[data-baseweb="popover"] {
        z-index: 999999 !important;
    }
    
    div[data-baseweb="calendar"] {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #1e293b !important;
        border-radius: 16px !important;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5) !important;
    }

    /* Contenedor fluido sin desbordamientos horizontales */
    div[data-testid="stDataFrame"] {
        width: 100% !important;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 16px;
        padding: 4px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }
    div[data-testid="stDataFrame"] > div {
        width: 100% !important;
        overflow-x: hidden !important;
    }

    /* Tarjetas de Encabezado Glassmorphism */
    .hero-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px 28px;
        margin-bottom: 25px;
        box-shadow: 0 20px 40px -15px rgba(0,0,0,0.7);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 30%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.03em;
    }

    .disclaimer-text {
        font-size: 0.78rem;
        color: #94a3b8;
        line-height: 1.5;
        margin-top: 8px;
        margin-bottom: 0;
        max-width: 650px;
    }

    .dolar-badge {
        text-align: right; 
        padding: 12px 18px; 
        background: rgba(250, 204, 21, 0.04); 
        border: 1px solid rgba(250, 204, 21, 0.15); 
        border-radius: 14px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    }

    .kpi-card {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.3) 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.3);
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #38bdf8;
        margin-top: 4px;
        letter-spacing: -0.02em;
    }
    .kpi-title {
        font-size: 0.75rem;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.08em;
    }

    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 30px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.01em;
    }

    /* Botones y Elementos Sidebar Estilizados */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.6);
    }
</style>
""", unsafe_allow_html=True)

OPCIONES_INDICADORES = ["EMAs Personalizadas", "Bandas Bollinger", "Supertrend", "VWAP", "Parabolic SAR", "MACD", "RSI (14)"]

if 'indicadores_activos' not in st.session_state:
    st.session_state['indicadores_activos'] = ["EMAs Personalizadas", "RSI (14)"]

if 'lista_emas' not in st.session_state:
    st.session_state['lista_emas'] = [
        {"periodo": 50, "color": "#38bdf8"},
        {"periodo": 100, "color": "#facc15"},
        {"periodo": 200, "color": "#a855f7"}
    ]

if 'empresa_seleccionada' not in st.session_state:
    st.session_state['empresa_seleccionada'] = None

# --- Función para formatear números en Bs ---
def fmt_bs(valor):
    if pd.isna(valor) or valor is None:
        return "0,00"
    try:
        s = f"{valor:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except:
        return "0,00"

# --- Obtener el dólar oficial con múltiples APIs de respaldo ---
def obtener_dolar_oficial():
    apis = [
        {"url": "https://api.exchangerate.host/latest?base=USD&symbols=VES", "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))},
        {"url": "https://open.er-api.com/v6/latest/USD", "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))},
        {"url": "https://api.exchangeratesapi.io/latest?base=USD&symbols=VES", "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))}
    ]
    
    for api in apis:
        try:
            response = requests.get(api["url"], timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data and data.get("rates") and data["rates"].get("VES"):
                    precio = data["rates"]["VES"]
                    fecha = data.get("date", datetime.now().strftime("%Y-%m-%d"))
                    if precio and precio > 0:
                        return precio, fecha
        except Exception:
            continue
    return 0, ""

@st.cache_data(ttl=300)
def get_dolar_con_cache():
    return obtener_dolar_oficial()

# --- Cambiar temporalidad (1 Día, 1 Semana, 1 Mes) ---
def cambiar_temporalidad(df, temporalidad):
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    if temporalidad == "1 Semana":
        df_resampled = df.resample('W').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
    elif temporalidad == "1 Mes":
        df_resampled = df.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
    else:
        df_resampled = df.reset_index()
        return df_resampled
        
    df_resampled.reset_index(inplace=True)
    return df_resampled

# -------------------------------------------------------------------
# 1. FUNCIÓN QUE CALCULA TODOS LOS INDICADORES TÉCNICOS
# -------------------------------------------------------------------
def calcular_indicadores(df, lista_emas):
    df = df.sort_values('Date').reset_index(drop=True)

    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    for i in range(14, len(df)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * 13 + gain.iloc[i]) / 14
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * 13 + loss.iloc[i]) / 14

    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI_Anterior'] = df['RSI'].shift(1)

    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['BB_lower'] = df['SMA20'] - (2 * df['STD20'])
    df['BB_upper'] = df['SMA20'] + (2 * df['STD20'])

    total_filas = len(df)
    for item in lista_emas:
        p = int(item['periodo'])
        if p > 0:
            if total_filas >= p:
                df[f'EMA_{p}'] = df['Close'].ewm(span=p, adjust=False).mean()
            else:
                df[f'EMA_{p}'] = df['Close'].ewm(span=max(2, total_filas // 2), adjust=False).mean()

    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean() if 'EMA_30' not in df.columns else df.get('EMA_30', df['Close'].ewm(span=30, adjust=False).mean())
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean() if 'EMA_60' not in df.columns else df.get('EMA_60', df['Close'].ewm(span=60, adjust=False).mean())

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR14'] = true_range.rolling(14).mean()

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum() if 'Volume' in df.columns else tp

    multiplier = 3
    period = 10
    hl2 = (df['High'] + df['Low']) / 2
    df['ATR_ST'] = true_range.rolling(period).mean()
    df['Basic_Upper'] = hl2 + (multiplier * df['ATR_ST'])
    df['Basic_Lower'] = hl2 - (multiplier * df['ATR_ST'])
    
    supertrend = [0.0] * len(df)
    direction = [1] * len(df)
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > df['Basic_Upper'].iloc[i-1]:
            direction[i] = 1
        elif df['Close'].iloc[i] < df['Basic_Lower'].iloc[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
            if direction[i] == 1 and df['Basic_Lower'].iloc[i] < df['Basic_Lower'].iloc[i-1]:
                df.loc[i, 'Basic_Lower'] = df['Basic_Lower'].iloc[i-1]
            if direction[i] == -1 and df['Basic_Upper'].iloc[i] > df['Basic_Upper'].iloc[i-1]:
                df.loc[i, 'Basic_Upper'] = df['Basic_Upper'].iloc[i-1]
        supertrend[i] = df['Basic_Lower'].iloc[i] if direction[i] == 1 else df['Basic_Upper'].iloc[i]
    df['Supertrend'] = supertrend

    psar = df['Close'].copy()
    af = 0.02
    max_af = 0.2
    is_long = True
    ep = df['High'].iloc[0]
    sar = df['Low'].iloc[0]
    
    for i in range(2, len(df)):
        if is_long:
            sar = sar + af * (ep - sar)
            sar = min(sar, df['Low'].iloc[i-1], df['Low'].iloc[i-2])
            if df['Low'].iloc[i] < sar:
                is_long = False
                sar = ep
                ep = df['Low'].iloc[i]
                af = 0.02
            else:
                if df['High'].iloc[i] > ep:
                    ep = df['High'].iloc[i]
                    af = min(af + 0.02, max_af)
        else:
            sar = sar + af * (ep - sar)
            sar = max(sar, df['High'].iloc[i-1], df['High'].iloc[i-2])
            if df['High'].iloc[i] > sar:
                is_long = True
                sar = ep
                ep = df['Low'].iloc[i]
                af = 0.02
            else:
                if df['Low'].iloc[i] < ep:
                    ep = df['Low'].iloc[i]
                    af = min(af + 0.02, max_af)
        psar.iloc[i] = sar
    df['Parabolic_SAR'] = psar

    return df

# -------------------------------------------------------------------
# GRÁFICO TÉCNICO INTERACTIVO (LÓGICA TRADINGVIEW: SCROLL ZOOM / ESCALA Y)
# -------------------------------------------------------------------
def generar_grafico_tecnico(df, nombre_empresa, temporalidad, indicadores_seleccionados, lista_emas):
    df_plot = df.copy()

    subpaneles = [ind for ind in indicadores_seleccionados if ind in ["MACD", "RSI (14)"]]
    num_subpaneles = len(subpaneles)

    if num_subpaneles == 1:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', subpaneles[0]), row_width=[0.20, 0.80]
        )
    elif num_subpaneles >= 2:
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', subpaneles[0], subpaneles[1]), row_width=[0.15, 0.15, 0.70]
        )
    else:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', 'VOLUMEN'), row_width=[0.20, 0.80]
        )

    fig.add_trace(go.Candlestick(
        x=df_plot['Date'], open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        name='Precio', increasing_line_color='#10b981', decreasing_line_color='#f43f5e',
        increasing_fillcolor='#10b981', decreasing_fillcolor='#f43f5e'
    ), row=1, col=1)

    if "EMAs Personalizadas" in indicadores_seleccionados:
        for item in lista_emas:
            p = int(item['periodo'])
            col = item['color']
            col_name = f'EMA_{p}'
            if col_name in df_plot.columns:
                fig.add_trace(go.Scatter(
                    x=df_plot['Date'], y=df_plot[col_name],
                    line=dict(color=col, width=1.3),
                    name=f'EMA {p}'
                ), row=1, col=1)

    if "Bandas Bollinger" in indicadores_seleccionados:
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_upper'], line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot'), name='BB Sup'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_lower'], line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dot'), name='BB Inf'), row=1, col=1)

    if "Supertrend" in indicadores_seleccionados:
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Supertrend'], mode='lines', line=dict(color='#a855f7', width=2), name='Supertrend'), row=1, col=1)

    if "VWAP" in indicadores_seleccionados:
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['VWAP'], line=dict(color='#3b82f6', width=1.5), name='VWAP'), row=1, col=1)

    if "Parabolic SAR" in indicadores_seleccionados:
        fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Parabolic_SAR'], mode='markers', marker=dict(color='#f97316', size=3), name='SAR'), row=1, col=1)

    fila_actual = 2
    if num_subpaneles == 0 and 'Volume' in df_plot.columns:
        colores_volumen = np.where(df_plot['Close'] >= df_plot['Open'], 'rgba(16, 185, 129, 0.6)', 'rgba(244, 63, 94, 0.6)')
        fig.add_trace(go.Bar(x=df_plot['Date'], y=df_plot['Volume'], marker_color=colores_volumen, name='Volumen'), row=fila_actual, col=1)
    
    for sub in subpaneles:
        if sub == "MACD":
            colores_hist = np.where(df_plot['MACD_Hist'] >= 0, 'rgba(16, 185, 129, 0.5)', 'rgba(244, 63, 94, 0.5)')
            fig.add_trace(go.Bar(x=df_plot['Date'], y=df_plot['MACD_Hist'], marker_color=colores_hist, name='Hist'), row=fila_actual, col=1)
            fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD'], line=dict(color='#38bdf8', width=1.2), name='MACD'), row=fila_actual, col=1)
            fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['MACD_Signal'], line=dict(color='#fb923c', width=1.2), name='Signal'), row=fila_actual, col=1)
        elif sub == "RSI (14)":
            fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['RSI'], line=dict(color='#facc15', width=1.5, shape='spline'), name='RSI'), row=fila_actual, col=1)
            fig.add_hline(y=70, line_dash="dot", row=fila_actual, col=1, line_color="rgba(244, 63, 94, 0.5)")
            fig.add_hline(y=30, line_dash="dot", row=fila_actual, col=1, line_color="rgba(16, 185, 129, 0.5)")
        fila_actual += 1

    fig.update_layout(
        height=850, 
        paper_bgcolor='#0b1120',
        plot_bgcolor='#0b1120',
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=25, b=10),
        hovermode='x unified',
        dragmode='pan',
        showlegend=False
    )
    
    # Comportamiento exacto TradingView: Zoom por scroll y escalado libre en eje Y
    fig.update_xaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False, fixedrange=False)
    fig.update_yaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False, fixedrange=False)
    
    return fig

# -------------------------------------------------------------------
# VISTA: TERMINAL ANALÍTICO GRÁFICO (PESTAÑA NUEVA)
# -------------------------------------------------------------------
def renderizar_vista_grafico(datos_empresa):
    if st.button("⬅️ Volver al Panel Principal"):
        st.session_state['empresa_seleccionada'] = None
        st.rerun()

    dolar, _ = get_dolar_con_cache()
    precio_usd = (datos_empresa['precio'] / dolar) if dolar > 0 else 0
    
    st.markdown(f"""
    <div class="hero-container" style="margin-bottom: 20px;">
        <div>
            <span class="main-title" style="font-size: 1.8rem;">📊 Terminal Gráfico: {datos_empresa['nombre']}</span>
            <span style="margin-left: 10px;" class="card-badge">{datos_empresa['estado']}</span>
        </div>
        <div style="display: flex; gap: 25px;">
            <div>
                <div class="metric-label">Precio Bs</div>
                <div class="metric-value" style="font-size: 1.1rem;">{fmt_bs(datos_empresa['precio'])}</div>
            </div>
            <div>
                <div class="metric-label">Precio USD</div>
                <div class="metric-value" style="font-size: 1.1rem;">${precio_usd:.4f}</div>
            </div>
            <div>
                <div class="metric-label">Upside</div>
                <div class="metric-value" style="font-size: 1.1rem; color: #4ade80;">+{datos_empresa['upside']:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_temp, col_ind = st.columns([1, 2])
    with col_temp:
        temporalidad = st.radio("Temporalidad", ["1 Día", "1 Semana", "1 Mes"], horizontal=True, label_visibility="collapsed")

    with col_ind:
        st.session_state['indicadores_activos'] = [
            ind for ind in st.session_state['indicadores_activos'] if ind in OPCIONES_INDICADORES
        ]
        
        indicadores_seleccionados = st.multiselect(
            "Seleccionar Indicadores:",
            OPCIONES_INDICADORES,
            default=st.session_state['indicadores_activos'],
            placeholder="Añadir indicadores técnicos..."
        )
        st.session_state['indicadores_activos'] = indicadores_seleccionados

    if "EMAs Personalizadas" in indicadores_seleccionados:
        with st.expander("⚙️ Configurar EMAs (Períodos y Colores)", expanded=False):
            nuevas_emas = []
            cols_emas = st.columns(len(st.session_state['lista_emas']) + 1)
            
            for idx, item in enumerate(st.session_state['lista_emas']):
                with cols_emas[idx]:
                    p = st.number_input(f"EMA #{idx+1}", min_value=1, max_value=500, value=int(item['periodo']), key=f"ema_p_{idx}")
                    c = st.color_picker(f"Color #{idx+1}", value=item['color'], key=f"ema_c_{idx}")
                    nuevas_emas.append({"periodo": p, "color": c})
            
            with cols_emas[-1]:
                st.write("")
                st.write("")
                if st.button("➕ Añadir EMA"):
                    nuevas_emas.append({"periodo": 50, "color": "#22c55e"})
                    st.session_state['lista_emas'] = nuevas_emas
                    st.rerun()
            
            st.session_state['lista_emas'] = nuevas_emas

    df_convertido = cambiar_temporalidad(datos_empresa['df_original'], temporalidad)
    df_indicadores = calcular_indicadores(df_convertido, st.session_state['lista_emas'])
    
    fig = generar_grafico_tecnico(df_indicadores, datos_empresa['nombre'], temporalidad, indicadores_seleccionados, st.session_state['lista_emas'])
    
    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={'scrollZoom': True, 'displayModeBar': False}
    )

# -------------------------------------------------------------------
# 2. FUNCIÓN QUE ANALIZA CADA ARCHIVO (ORIGINAL BVC)
# -------------------------------------------------------------------
def analizar_archivo(ruta_archivo, fecha_referencia):
    try:
        df = pd.read_csv(ruta_archivo, decimal=',', thousands='.')
        df.columns = df.columns.str.replace('.CR', '').str.strip()

        for col in ['Close', 'High', 'Low', 'Open', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df[col] = 0.0

        df = df.dropna(subset=['Close', 'High', 'Low', 'Open'])

        if len(df) < 30:
            return None

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])

        fecha_limite = pd.to_datetime(fecha_referencia)
        df = df[df['Date'] <= fecha_limite]

        if df.empty:
            return {
                'nombre': os.path.basename(ruta_archivo).replace('.csv', ''),
                'estado': '❌ Sin Datos',
                'puntaje': 0,
                'precio': 0,
                'target': 0,
                'upside': 0,
                'df_original': df
            }

        df = df.sort_values('Date').reset_index(drop=True)

        df_con_volumen = df[df['Volume'] > 0] if 'Volume' in df.columns else pd.DataFrame()
        if df_con_volumen.empty:
            ultimo = df.iloc[-1]
        else:
            ultimo = df_con_volumen.iloc[-1]

        df_calculado = calcular_indicadores(df.copy(), st.session_state['lista_emas'])

        ultimo_fila = df_calculado[df_calculado['Date'] == ultimo['Date']]
        if ultimo_fila.empty:
            ultimo_datos = df_calculado.iloc[-1]
        else:
            ultimo_datos = ultimo_fila.iloc[-1]

        # ---------------------------------------------------------------
        # PUNTAJE: ESTRATEGIA ORIGINAL BVC (Máximo 100 puntos)
        # ---------------------------------------------------------------
        puntaje = 0

        if ultimo_datos['EMA30'] < ultimo_datos['EMA60']:
            puntaje += 25

        if not pd.isna(ultimo_datos['EMA60']) and ultimo_datos['EMA60'] > 0:
            distancia_ema = ((ultimo_datos['EMA60'] - ultimo_datos['Close']) / ultimo_datos['EMA60']) * 100
            if distancia_ema > 0:
                pts_ema = min(distancia_ema * 1.6, 40)
                puntaje += pts_ema

        if not pd.isna(ultimo_datos['BB_lower']) and ultimo_datos['Close'] < ultimo_datos['BB_lower']:
            puntaje += 15

        rsi_hoy = ultimo_datos['RSI']
        rsi_ayer = ultimo_datos['RSI_Anterior']
        if not pd.isna(rsi_hoy):
            distancia_al_30 = abs(rsi_hoy - 30)
            pts_nivel = max(0, 10 - distancia_al_30)
            puntaje += pts_nivel

        if not pd.isna(rsi_hoy) and not pd.isna(rsi_ayer):
            if rsi_hoy > rsi_ayer and rsi_hoy < 40:
                puntaje += 10

        if not pd.isna(ultimo_datos['ATR14']) and ultimo_datos['ATR14'] > 0:
            target = ultimo_datos['Close'] + (1.5 * ultimo_datos['ATR14'])
            upside = ((target - ultimo_datos['Close']) / ultimo_datos['Close']) * 100
            if upside > 20:
                puntaje += 10
            elif upside > 10:
                puntaje += 5
        else:
            target, upside = 0, 0

        if 'EMA100' in ultimo_datos and not pd.isna(ultimo_datos['EMA100']) and ultimo_datos['Close'] < ultimo_datos['EMA100']:
            puntaje += 5

        puntaje = min(puntaje, 100)

        if puntaje >= 60 and ultimo_datos['EMA30'] < ultimo_datos['EMA60']:
            estado = '✅ COMPRA'
        elif puntaje >= 35:
            estado = '🔍 SEGUIMIENTO'
        else:
            estado = '⏸️ ESPERAR'

        return {
            'nombre': os.path.basename(ruta_archivo).replace('.csv', ''),
            'estado': estado,
            'puntaje': round(puntaje, 1),
            'precio': float(ultimo_datos['Close']),
            'target': float(target),
            'upside': float(upside),
            'df_original': df
        }

    except Exception:
        return None

# -------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO Y CONFIGURACIÓN LATERAL
# -------------------------------------------------------------------
st.sidebar.markdown("<p style='font-size: 0.85rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;'>📅 Fecha de Referencia</p>", unsafe_allow_html=True)

fecha_referencia = st.sidebar.date_input(
    "Seleccionar fecha",
    value=date.today(),
    label_visibility="collapsed"
)

carpeta = "./datos_bvc"

# --- Cabecera con Título a la izquierda, Descargo y Dólar a la derecha ---
col_titulo, col_dolar = st.columns([2, 1])

with col_titulo:
    st.markdown("""
    <div class="hero-container">
        <div>
            <h1 class="main-title">📊 Análisis BVC</h1>
            <p class="disclaimer-text">
                <strong>Descargo de responsabilidad:</strong> En ningún momento se promueve o se indica la compra de ninguna acción. La misma es sólo responsabilidad personal.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_dolar:
    with st.spinner("Cargando dólar..."):
        dolar_oficial, fecha_dolar = get_dolar_con_cache()
        if dolar_oficial > 0:
            st.markdown(f"""
            <div class="dolar-badge">
                <p style="margin: 0; font-weight: 800; font-size: 1.25rem; color: #facc15;">
                    💵 Dólar BCV: <strong>{fmt_bs(dolar_oficial)} Bs/USD</strong>
                </p>
                <p style="margin: 0; font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">
                    Cierre Oficial: {fecha_dolar}
                </p>
            </div>
            """, unsafe_allow_html=True)

st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("🔍 Analizar Carpeta", use_container_width=True, type="primary"):
    if not os.path.exists(carpeta):
        os.makedirs(carpeta, exist_ok=True)
        st.error("⚠️ La carpeta `./datos_bvc` no existía, se ha creado vacía. Coloca tus CSV dentro.")
    else:
        archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
        if not archivos:
            st.warning("No se encontraron archivos .csv en la carpeta `./datos_bvc`.")
        else:
            resultados = []
            with st.spinner(f"Analizando {len(archivos)} archivos hasta {fecha_referencia.strftime('%Y-%m-%d')}..."):
                for archivo in archivos:
                    ruta_completa = os.path.join(carpeta, archivo)
                    res = analizar_archivo(ruta_completa, fecha_referencia)
                    if res:
                        resultados.append(res)

            if not resultados:
                st.error("❌ No se pudo procesar ningún archivo.")
            else:
                st.session_state['resultados'] = resultados

# --- RENDERIZADO PRINCIPAL O VISTA DE GRÁFICO EN PESTAÑA NUEVA ---
if st.session_state['empresa_seleccionada'] is not None:
    renderizar_vista_grafico(st.session_state['empresa_seleccionada'])
else:
    # Mostrar resultados si están en session_state
    if 'resultados' in st.session_state and st.session_state['resultados']:
        df_resultados = pd.DataFrame(st.session_state['resultados'])
        
        df_activos = df_resultados[~df_resultados['estado'].isin(['❌ Sin Datos', '⚠️ ERROR'])].copy()
        if not df_activos.empty:
            df_activos = df_activos.sort_values('puntaje', ascending=False)

            dolar, _ = get_dolar_con_cache()
            if dolar > 0:
                df_activos['precio_usd'] = df_activos['precio'] / dolar

                total_compras = len(df_activos[df_activos['estado'].str.contains('COMPRA', case=False, na=False)])
                top_accion = df_activos.sort_values('puntaje', ascending=False).iloc[0]
                
                st.markdown("<br>", unsafe_allow_html=True)
                kpi1, kpi2, kpi3 = st.columns(3)
                with kpi1:
                    st.markdown(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Oportunidades de Compra</div>
                        <div class="kpi-value" style="color: #4ade80;">{total_compras} Acciones</div>
                    </div>
                    """, unsafe_allow_html=True)
                with kpi2:
                    st.markdown(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Top Oportunidad #1</div>
                        <div class="kpi-value" style="color: #facc15; font-size: 1.4rem;">{top_accion['nombre']} ({top_accion['puntaje']} pts)</div>
                    </div>
                    """, unsafe_allow_html=True)
                with kpi3:
                    st.markdown(f"""
                    <div class="kpi-card">
                        <div class="kpi-title">Máximo Upside Estimado</div>
                        <div class="kpi-value" style="color: #38bdf8;">+{top_accion['upside']:.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                def mostrar_tabla_interactiva(df, titulo, clave_tabla):
                    if df.empty:
                        return
                    
                    df_display = df.copy()
                    df_display = df_display.rename(columns={'estado': 'Recomendado', 'nombre': 'Ticker'})
                    
                    columnas_mostrar = ['Ticker', 'Recomendado', 'puntaje', 'precio', 'precio_usd', 'target', 'upside']
                    
                    st.markdown(f"""
                    <div class="section-header">
                        <span>📈 {titulo}</span> 
                        <span style="font-size: 0.85rem; font-weight: 500; color: #64748b;">({len(df)} empresas)</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    evento = st.dataframe(
                        df_display[columnas_mostrar], 
                        use_container_width=True, 
                        hide_index=True,
                        height=min(450, (len(df) + 1) * 38 + 12),
                        selection_mode="single-row",
                        on_select="rerun",
                        key=clave_tabla,
                        column_config={
                            "Ticker": st.column_config.Column(
                                "Ticker", 
                                help="Haz clic en cualquier Ticker para abrir el gráfico analítico en pestaña completa",
                                width="small"
                            ),
                            "Recomendado": st.column_config.TextColumn("Recomendación", width="medium"),
                            "puntaje": st.column_config.ProgressColumn("Puntaje", format="%f pts", min_value=0, max_value=100, width="small"),
                            "precio": st.column_config.NumberColumn("Precio (Bs)", format="%.2f Bs", width="small"),
                            "precio_usd": st.column_config.NumberColumn("Precio (USD)", format="$%.4f", width="small"),
                            "target": st.column_config.NumberColumn("Target (Bs)", format="%.2f Bs", width="small"),
                            "upside": st.column_config.NumberColumn("Upside", format="+%.2f%%", width="small")
                        }
                    )
                    
                    if evento:
                        filas_seleccionadas = evento.get("selection", {}).get("rows", [])
                        if filas_seleccionadas:
                            indice_fila = filas_seleccionadas[0]
                            nombre_empresa_tocada = df_display.iloc[indice_fila]['Ticker']
                            datos_empresa = next((item for item in st.session_state['resultados'] if item["nombre"] == nombre_empresa_tocada), None)
                            if datos_empresa:
                                st.session_state['empresa_seleccionada'] = datos_empresa
                                st.rerun()

                mostrar_tabla_interactiva(df_activos[df_activos['precio_usd'] < 1], "Acciones Menores a 1 USD", "tabla_menos_1")
                st.markdown("<br>", unsafe_allow_html=True)
                mostrar_tabla_interactiva(df_activos[df_activos['precio_usd'] >= 1], "Acciones Mayores o Iguales a 1 USD", "tabla_mas_1")

    else:
        st.info("👈 Selecciona una fecha en el calendario de la barra lateral y presiona 'Analizar Carpeta'.")
