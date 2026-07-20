import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
import subprocess
import sys
from datetime import datetime, date
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------------------------
st.set_page_config(page_title="Analizador BVC - Premium", layout="wide")

# ESTILOS CSS PERSONALIZADOS PARA UN MODAL ELEGANTE
st.markdown("""
<style>
    /* Fondo oscuro y tipografía refinada */
    .stApp {
        background-color: #050505;
    }
    
    /* Estilos del Modal */
    div[role="dialog"] {
        background-color: #0a0a0c !important;
        border: 1px solid #1e293b !important;
        border-radius: 16px !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8) !important;
    }

    /* Tarjeta resumida del Modal */
    .header-card {
        background: linear-gradient(135deg, #111827 0%, #0f172a 100%);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .card-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
    }
    
    .card-badge {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .metric-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f8fafc;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

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

# --- Obtener el dólar oficial ---
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

@st.cache_data(ttl=3600)
def get_dolar_con_cache():
    return obtener_dolar_oficial()

# -------------------------------------------------------------------
# 1. TEMPORALIDADES (RESAMPLING)
# -------------------------------------------------------------------
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
# 2. CÁLCULO DE INDICADORES
# -------------------------------------------------------------------
def calcular_indicadores(df):
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
    rsi_raw = 100 - (100 / (1 + rs))
    
    df['RSI'] = rsi_raw.ewm(span=3, adjust=False).mean()
    df['RSI_Anterior'] = df['RSI'].shift(1)

    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['BB_lower'] = df['SMA20'] - (2 * df['STD20'])
    df['BB_upper'] = df['SMA20'] + (2 * df['STD20'])

    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    df['EMA100'] = df['Close'].ewm(span=100, adjust=False).mean()

    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR14'] = true_range.rolling(14).mean()

    return df

# -------------------------------------------------------------------
# 3. DISEÑO GRÁFICO ULTRA-ELEGANTE (SIN RSI)
# -------------------------------------------------------------------
def generar_grafico_tecnico(df, nombre_empresa, temporalidad):
    df_plot = df.tail(100).copy()

    # 3 Pisos: Precio (60%), Volumen (20%), MACD (20%)
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        subplot_titles=('PRECIO', 'VOLUMEN', 'MACD'),
        row_width=[0.20, 0.20, 0.60]
    )

    # 1. VELAS JAPONESAS
    fig.add_trace(go.Candlestick(
        x=df_plot['Date'], open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        name='Precio',
        increasing_line_color='#10b981', decreasing_line_color='#f43f5e',
        increasing_fillcolor='#10b981', decreasing_fillcolor='#f43f5e'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['EMA30'], line=dict(color='#38bdf8', width=1.2), name='EMA 30'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['EMA60'], line=dict(color='#fb7185', width=1.2), name='EMA 60'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_upper'], line=dict(color='rgba(255,255,255,0.15)', width=1, dash='dot'), name='BB Sup'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_lower'], line=dict(color='rgba(255,255,255,0.15)', width=1, dash='dot'), name='BB Inf'), row=1, col=1)

    # 2. VOLUMEN
    colores_volumen = np.where(df_plot['Close'] >= df_plot['Open'], 'rgba(16, 185, 129, 0.6)', 'rgba(244, 63, 94, 0.6)')
    fig.add_trace(go.Bar(
        x=df_plot['Date'], y=df_plot['Volume'],
        marker_color=colores_volumen, name='Volumen'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df_plot['Date'], y=df_plot['Vol_MA20'],
        line=dict(color='#f59e0b', width=1.2), name='Vol MA20'
    ), row=2, col=1)

    # 3. MACD
    colores_hist = np.where(df_plot['MACD_Hist'] >= 0, 'rgba(16, 185, 129, 0.5)', 'rgba(244, 63, 94, 0.5)')
    fig.add_trace(go.Bar(
        x=df_plot['Date'], y=df_plot['MACD_Hist'],
        marker_color=colores_hist, name='Hist'
    ), row=3, col=1)

    fig.add_trace(go.Scatter(
        x=df_plot['Date'], y=df_plot['MACD'],
        line=dict(color='#38bdf8', width=1.2), name='MACD'
    ), row=3, col=1)

    fig.add_trace(go.Scatter(
        x=df_plot['Date'], y=df_plot['MACD_Signal'],
        line=dict(color='#fb923c', width=1.2), name='Signal'
    ), row=3, col=1)

    # ESTILIZACIÓN MINIMALISTA Y ELEGANTE
    fig.update_layout(
        height=720, 
        paper_bgcolor='#0a0a0c',
        plot_bgcolor='#0a0a0c',
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=25, b=10),
        hovermode='x unified',
        dragmode='pan',
        showlegend=False
    )
    
    fig.update_xaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='#1e293b', gridwidth=0.5, zeroline=False)
    
    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(size=11, color='#64748b', family='Segoe UI')
    
    return fig

# -------------------------------------------------------------------
# 4. LEER Y PROCESAR ARCHIVO CSV
# -------------------------------------------------------------------
def analizar_archivo(ruta_archivo, fecha_referencia):
    try:
        df = pd.read_csv(ruta_archivo, decimal=',', thousands='.')
        df.columns = df.columns.str.replace('.CR', '').str.strip()

        for col in ['Close', 'High', 'Low', 'Open', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(subset=['Close', 'High', 'Low', 'Open'])

        if len(df) < 30:
            return None

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])

        fecha_limite = pd.to_datetime(fecha_referencia)
        df = df[df['Date'] <= fecha_limite]

        if df.empty:
            return None

        df = df.sort_values('Date').reset_index(drop=True)

        df_con_volumen = df[df['Volume'] > 0]
        if df_con_volumen.empty:
            ultimo = df.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')
        else:
            ultimo = df_con_volumen.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')

        df_calculado = calcular_indicadores(df.copy())

        ultimo_fila = df_calculado[df_calculado['Date'] == ultimo['Date']]
        if ultimo_fila.empty:
            ultimo_datos = df_calculado.iloc[-1]
        else:
            ultimo_datos = ultimo_fila.iloc[-1]

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
            target = 0
            upside = 0

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
            'rsi': round(rsi_hoy, 2) if not pd.isna(rsi_hoy) else 0,
            'rsi_ayer': round(rsi_ayer, 2) if not pd.isna(rsi_ayer) else 0,
            'ema30': float(ultimo_datos['EMA30']) if not pd.isna(ultimo_datos['EMA30']) else 0,
            'ema60': float(ultimo_datos['EMA60']) if not pd.isna(ultimo_datos['EMA60']) else 0,
            'fecha_ultimo': fecha_ultimo_operado,
            'df_original': df
        }

    except Exception as e:
        return None

# -------------------------------------------------------------------
# 5. MODAL ELEGANTE REDISEÑADO
# -------------------------------------------------------------------
if 'empresa_modal' not in st.session_state:
    st.session_state['empresa_modal'] = None

@st.dialog(" Análitica de Mercado", width="large")
def mostrar_modal_grafico(datos_empresa):
    dolar, _ = get_dolar_con_cache()
    precio_usd = (datos_empresa['precio'] / dolar) if dolar > 0 else 0
    
    # Tarjeta de Cabecera Flotante Eleganter (Sin RSI)
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
                <div class="metric-label">Potencial</div>
                <div class="metric-value" style="color: #4ade80;">+{datos_empresa['upside']:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_temp, col_esp = st.columns([2, 3])
    with col_temp:
        temporalidad = st.radio("Temporalidad", ["1 Día", "1 Semana", "1 Mes"], horizontal=True, label_visibility="collapsed")

    df_convertido = cambiar_temporalidad(datos_empresa['df_original'], temporalidad)
    df_indicadores = calcular_indicadores(df_convertido)
    fig = generar_grafico_tecnico(df_indicadores, datos_empresa['nombre'], temporalidad)
    
    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={'scrollZoom': True, 'displayModeBar': False}
    )

# -------------------------------------------------------------------
# 6. INTERFAZ PRINCIPAL
# -------------------------------------------------------------------
st.sidebar.subheader("📥 Datos de la Bolsa")
fecha_referencia = st.sidebar.date_input("📅 Fecha de referencia", value=date.today())

st.sidebar.divider()
if st.sidebar.button("🔄 Actualizar Historial BVC", use_container_width=True):
    with st.spinner("Descargando datos históricos..."):
        try:
            subprocess.run([sys.executable, "descargador_cascada.py"], capture_output=True, text=True)
            st.sidebar.success("🎉 ¡Historial actualizado!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

st.sidebar.divider()
btn_analizar = st.sidebar.button("🔍 Analizar Mercado", use_container_width=True, type="primary")

# --- CABECERA PRINCIPAL ---
col_titulo, col_dolar = st.columns([2, 1])

with col_titulo:
    st.title("📊 Terminal Analítico BVC")
    st.markdown("**Bolsa de Valores de Caracas** - Estrategia cuantitativa sin volumen.")

with col_dolar:
    with st.spinner("Cargando dólar..."):
        dolar_oficial, fecha_dolar = get_dolar_con_cache()
        if dolar_oficial > 0:
            st.markdown(f"""
            <div style="text-align: right; padding: 10px; background: transparent; border-radius: 12px; margin-top: 5px;">
                <p style="margin: 0; font-weight: 700; font-size: 1.2rem; color: #facc15;">
                    💵 Precio $ BCV: <strong>{fmt_bs(dolar_oficial)} Bs/USD</strong>
                </p>
                <p style="margin: 0; font-size: 0.7rem; color: #94a3b8;">
                    Actualizado: {fecha_dolar}
                </p>
            </div>
            """, unsafe_allow_html=True)

carpeta = "./datos_bvc"

if btn_analizar:
    if not os.path.exists(carpeta):
        st.error("⚠️ La carpeta de datos aún no existe. Presiona 'Actualizar Historial BVC'.")
    else:
        archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
        if not archivos:
            st.warning("No hay datos descargados. Presiona 'Actualizar Historial BVC'.")
        else:
            resultados = []
            with st.spinner("Procesando datos del mercado..."):
                for archivo in archivos:
                    res = analizar_archivo(os.path.join(carpeta, archivo), fecha_referencia)
                    if res:
                        resultados.append(res)

            if resultados:
                st.session_state['resultados'] = resultados
                st.session_state['analizado'] = True

if st.session_state.get('analizado', False):
    resultados = st.session_state['resultados']
    df_resultados = pd.DataFrame(resultados)
    
    dolar, _ = get_dolar_con_cache()
    if dolar > 0:
        df_resultados['precio_usd'] = df_resultados['precio'] / dolar

        df_menos_1 = df_resultados[df_resultados['precio_usd'] < 1].sort_values('puntaje', ascending=False)
        df_mas_1 = df_resultados[df_resultados['precio_usd'] >= 1].sort_values('puntaje', ascending=False)

        def mostrar_tabla_interactiva(df, titulo, clave_tabla):
            if df.empty:
                return
            
            df_display = df.copy()
            df_display = df_display.rename(columns={'estado': 'Recomendado'})
            for col in ['precio', 'target', 'ema30', 'ema60']:
                df_display[col] = df_display[col].apply(fmt_bs)
            df_display['precio_usd'] = df_display['precio_usd'].apply(lambda x: f"{x:.4f}")
            df_display['upside'] = df_display['upside'].apply(lambda x: f"{x:.2f}%")
            df_display['rsi'] = df_display['rsi'].apply(lambda x: f"{x:.2f}")

            columnas = ['nombre', 'fecha_ultimo', 'Recomendado', 'puntaje', 'precio', 'precio_usd', 'target', 'upside', 'rsi', 'ema30', 'ema60']
            
            st.subheader(f"📊 {titulo} ({len(df)} acciones)")
            st.caption("💡 Haz clic en una fila para desplegar la analítica de la empresa.")
            
            evento = st.dataframe(
                df_display[columnas], 
                use_container_width=True, 
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun",
                key=clave_tabla
            )
            
            filas_seleccionadas = evento.selection.get("rows", [])
            if filas_seleccionadas:
                indice_fila = filas_seleccionadas[0]
                nombre_empresa_tocada = df_display.iloc[indice_fila]['nombre']
                datos_empresa = next((item for item in resultados if item["nombre"] == nombre_empresa_tocada), None)
                if datos_empresa:
                    st.session_state['empresa_modal'] = datos_empresa

        st.subheader(f"📈 Oportunidades del Mercado - {fecha_referencia.strftime('%Y-%m-%d')}")
        
        mostrar_tabla_interactiva(df_menos_1, "🔽 Acciones Menores a 1 USD", "tabla_menos_1")
        mostrar_tabla_interactiva(df_mas_1, "🔼 Acciones Mayores o Iguales a 1 USD", "tabla_mas_1")

        if st.session_state['empresa_modal'] is not None:
            mostrar_modal_grafico(st.session_state['empresa_modal'])

else:
    st.info("👈 Presiona 'Analizar Mercado' en el menú lateral para desplegar las tablas.")
