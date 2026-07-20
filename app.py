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
st.set_page_config(page_title="Terminal Analítico BVC - Premium", layout="wide")

# ESTILOS CSS PERSONALIZADOS DE ALTA GAMA (DARK ULTIMATE & TABLAS EXPANDIDAS)
st.markdown("""
<style>
    .stApp {
        background-color: #030712;
        color: #f3f4f6;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #090d16 !important;
        border-right: 1px solid #1f2937;
        padding-top: 1rem;
    }

    /* Corrección para que el popover del calendario se vea completo */
    div[data-baseweb="popover"] {
        z-index: 999999 !important;
    }
    
    div[data-baseweb="calendar"] {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #334151 !important;
        border-radius: 12px !important;
    }

    div[role="dialog"] {
        background-color: #090d16 !important;
        border: 1px solid #374151 !important;
        border-radius: 16px !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.9) !important;
    }

    /* Forzar que las tablas ocupen todo el ancho horizontal disponible */
    div[data-testid="stDataFrame"] {
        width: 100% !important;
    }
    div[data-testid="stDataFrame"] > div {
        width: 100% !important;
    }

    .header-card {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    
    .card-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.02em;
    }
    
    .card-badge {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
    }

    .metric-value {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f9fafb;
    }
    
    .metric-label {
        font-size: 0.72rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .kpi-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #38bdf8;
    }
    .kpi-title {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 600;
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

if 'empresa_modal' not in st.session_state:
    st.session_state['empresa_modal'] = None

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

    # RSI 14 (Método Wilder)
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

    # Bandas de Bollinger (20,2)
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['BB_lower'] = df['SMA20'] - (2 * df['STD20'])
    df['BB_upper'] = df['SMA20'] + (2 * df['STD20'])

    # EMAs configuradas dinámicamente
    total_filas = len(df)
    for item in lista_emas:
        p = int(item['periodo'])
        if p > 0:
            if total_filas >= p:
                df[f'EMA_{p}'] = df['Close'].ewm(span=p, adjust=False).mean()
            else:
                df[f'EMA_{p}'] = df['Close'].ewm(span=max(2, total_filas // 2), adjust=False).mean()

    # EMAs específicas para la estrategia base
    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean() if 'EMA_30' not in df.columns else df.get('EMA_30', df['Close'].ewm(span=30, adjust=False).mean())
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean() if 'EMA_60' not in df.columns else df.get('EMA_60', df['Close'].ewm(span=60, adjust=False).mean())

    # ATR (14)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR14'] = true_range.rolling(14).mean()

    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # VWAP
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum() if 'Volume' in df.columns else tp

    # Supertrend
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

    # Parabolic SAR
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
                ep = df['High'].iloc[i]
                af = 0.02
            else:
                if df['Low'].iloc[i] < ep:
                    ep = df['Low'].iloc[i]
                    af = min(af + 0.02, max_af)
        psar.iloc[i] = sar
    df['Parabolic_SAR'] = psar

    return df

# -------------------------------------------------------------------
# GRÁFICO TÉCNICO INTERACTIVO (PLOTLY)
# -------------------------------------------------------------------
def generar_grafico_tecnico(df, nombre_empresa, temporalidad, indicadores_seleccionados, lista_emas):
    df_plot = df.tail(100).copy()

    subpaneles = [ind for ind in indicadores_seleccionados if ind in ["MACD", "RSI (14)"]]
    num_subpaneles = len(subpaneles)

    if num_subpaneles == 1:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', subpaneles[0]), row_width=[0.25, 0.75]
        )
    elif num_subpaneles >= 2:
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', subpaneles[0], subpaneles[1]), row_width=[0.20, 0.20, 0.60]
        )
    else:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
            subplot_titles=('PRECIO', 'VOLUMEN'), row_width=[0.25, 0.75]
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
        height=720, 
        paper_bgcolor='#090d16',
        plot_bgcolor='#090d16',
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=25, b=10),
        hovermode='x unified',
        dragmode='pan',
        showlegend=False
    )
    
    fig.update_xaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False)
    
    return fig

# -------------------------------------------------------------------
# MODAL / DIÁLOGO GRÁFICO PROFESIONAL
# -------------------------------------------------------------------
@st.dialog("📊 Terminal Analítico Gráfico", width="large")
def mostrar_modal_grafico(datos_empresa):
    dolar, _ = get_dolar_con_cache()
    precio_usd = (datos_empresa['precio'] / dolar) if dolar > 0 else 0
    
    st.markdown(f"""
    <div class="header-card">
        <div>
            <span class="card-title">{datos_empresa['nombre']}</span>
            <span style="margin-left: 10px;" class="card-badge">{datos_empresa['estado']}</span>
        </div>
        <div style="display: flex; gap: 25px;">
            <div>
                <div class="metric-label">Precio Bs</div>
                <div class="metric-value">{fmt_bs(datos_empresa['precio'])}</div>
            </div>
            <div>
                <div class="metric-label">Precio USD</div>
                <div class="metric-value">${precio_usd:.4f}</div>
            </div>
            <div>
                <div class="metric-label">Upside</div>
                <div class="metric-value" style="color: #4ade80;">+{datos_empresa['upside']:.1f}%</div>
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
                'fecha_ultimo': fecha_referencia.strftime('%Y-%m-%d'),
                'df_original': df
            }

        df = df.sort_values('Date').reset_index(drop=True)

        df_con_volumen = df[df['Volume'] > 0] if 'Volume' in df.columns else pd.DataFrame()
        if df_con_volumen.empty:
            ultimo = df.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')
        else:
            ultimo = df_con_volumen.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')

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

        # 1. TENDENCIA (EMA 30 vs 60)
        if ultimo_datos['EMA30'] < ultimo_datos['EMA60']:
            puntaje += 25

        # 2. DISTANCIA A EMA 60
        if not pd.isna(ultimo_datos['EMA60']) and ultimo_datos['EMA60'] > 0:
            distancia_ema = ((ultimo_datos['EMA60'] - ultimo_datos['Close']) / ultimo_datos['EMA60']) * 100
            if distancia_ema > 0:
                pts_ema = min(distancia_ema * 1.6, 40)
                puntaje += pts_ema

        # 3. BOLLINGER
        if not pd.isna(ultimo_datos['BB_lower']) and ultimo_datos['Close'] < ultimo_datos['BB_lower']:
            puntaje += 15

        # 4. RSI - NIVEL
        rsi_hoy = ultimo_datos['RSI']
        rsi_ayer = ultimo_datos['RSI_Anterior']
        if not pd.isna(rsi_hoy):
            distancia_al_30 = abs(rsi_hoy - 30)
            pts_nivel = max(0, 10 - distancia_al_30)
            puntaje += pts_nivel

        # 5. RSI - PENDIENTE
        if not pd.isna(rsi_hoy) and not pd.isna(rsi_ayer):
            if rsi_hoy > rsi_ayer and rsi_hoy < 40:
                puntaje += 10

        # 6. POTENCIAL ATR
        if not pd.isna(ultimo_datos['ATR14']) and ultimo_datos['ATR14'] > 0:
            target = ultimo_datos['Close'] + (1.5 * ultimo_datos['ATR14'])
            upside = ((target - ultimo_datos['Close']) / ultimo_datos['Close']) * 100
            if upside > 20:
                puntaje += 10
            elif upside > 10:
                puntaje += 5
        else:
            target, upside = 0, 0

        # 7. BONUS EMA100
        if 'EMA100' in ultimo_datos and not pd.isna(ultimo_datos['EMA100']) and ultimo_datos['Close'] < ultimo_datos['EMA100']:
            puntaje += 5

        puntaje = min(puntaje, 100)

        # CLASIFICACIÓN
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
            'fecha_ultimo': fecha_ultimo_operado,
            'df_original': df
        }

    except Exception:
        return None

# -------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO Y CONFIGURACIÓN LATERAL
# -------------------------------------------------------------------
st.sidebar.subheader("📅 Fecha de Referencia")

fecha_referencia = st.sidebar.date_input(
    "Seleccionar fecha",
    value=date.today(),
    label_visibility="collapsed"
)

carpeta = "./datos_bvc"

# --- Cabecera con Título a la izquierda y Dólar a la derecha ---
col_titulo, col_dolar = st.columns([2, 1])

with col_titulo:
    st.title("📊 Terminal Analítico BVC")
    st.markdown("**Estrategia técnica** - Basada en Precio, EMA, RSI y ATR.")

with col_dolar:
    with st.spinner("Cargando dólar..."):
        dolar_oficial, fecha_dolar = get_dolar_con_cache()
        if dolar_oficial > 0:
            st.markdown(f"""
            <div style="text-align: right; padding: 10px; background: rgba(250, 204, 21, 0.05); border: 1px solid rgba(250, 204, 21, 0.2); border-radius: 12px; margin-top: 5px;">
                <p style="margin: 0; font-weight: 800; font-size: 1.25rem; color: #facc15;">
                    💵 Dólar BCV: <strong>{fmt_bs(dolar_oficial)} Bs/USD</strong>
                </p>
                <p style="margin: 0; font-size: 0.7rem; color: #94a3b8;">
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
            
            st.divider()
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
                    <div class="kpi-value" style="color: #facc15;">{top_accion['nombre']} ({top_accion['puntaje']} pts)</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi3:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">Máximo Upside Estimado</div>
                    <div class="kpi-value" style="color: #38bdf8;">+{top_accion['upside']:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

            st.divider()

            df_menos_1 = df_activos[df_activos['precio_usd'] < 1].copy()
            df_mas_1 = df_activos[df_activos['precio_usd'] >= 1].copy()

            def mostrar_tabla_interactiva(df, titulo, clave_tabla):
                if df.empty:
                    return
                
                df_display = df.copy()
                df_display = df_display.rename(columns={'estado': 'Recomendado'})
                
                columnas_mostrar = ['nombre', 'fecha_ultimo', 'Recomendado', 'puntaje', 'precio', 'precio_usd', 'target', 'upside']
                
                st.subheader(f"📊 {titulo} ({len(df)} empresas)")
                
                st.dataframe(
                    df_display[columnas_mostrar], 
                    use_container_width=True, 
                    hide_index=True,
                    height=min(480, (len(df) + 1) * 35 + 10),
                    selection_mode="single-row",
                    on_select="rerun",
                    key=clave_tabla,
                    column_config={
                        "nombre": st.column_config.TextColumn("Ticker", width="medium"),
                        "fecha_ultimo": st.column_config.TextColumn("Último Día", width="medium"),
                        "Recomendado": st.column_config.TextColumn("Recomendación", width="medium"),
                        "puntaje": st.column_config.ProgressColumn("Puntaje", format="%f pts", min_value=0, max_value=100, width="large"),
                        "precio": st.column_config.NumberColumn("Precio (Bs)", format="%.2f Bs", width="medium"),
                        "precio_usd": st.column_config.NumberColumn("Precio (USD)", format="$%.4f", width="medium"),
                        "target": st.column_config.NumberColumn("Target (Bs)", format="%.2f Bs", width="medium"),
                        "upside": st.column_config.NumberColumn("Upside", format="+%.2f%%", width="medium")
                    }
                )
                
                evento = st.session_state.get(clave_tabla)
                if evento:
                    filas_seleccionadas = evento.get("selection", {}).get("rows", [])
                    if filas_seleccionadas:
                        indice_fila = filas_seleccionadas[0]
                        nombre_empresa_tocada = df_display.iloc[indice_fila]['nombre']
                        datos_empresa = next((item for item in st.session_state['resultados'] if item["nombre"] == nombre_empresa_tocada), None)
                        if datos_empresa:
                            st.session_state['empresa_modal'] = datos_empresa

            mostrar_tabla_interactiva(df_menos_1, "Acciones Menores a 1 USD", "tabla_menos_1")
            st.markdown("<br>", unsafe_allow_html=True)
            mostrar_tabla_interactiva(df_mas_1, "Acciones Mayores o Iguales a 1 USD", "tabla_mas_1")

            if st.session_state['empresa_modal'] is not None:
                mostrar_modal_grafico(st.session_state['empresa_modal'])

else:
    st.info("👈 Selecciona una fecha en el calendario de la barra lateral y presiona 'Analizar Carpeta'.")
