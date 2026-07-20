import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime, date

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

if 'lista_emas' not in st.session_state:
    st.session_state['lista_emas'] = [
        {"periodo": 50, "color": "#38bdf8"},
        {"periodo": 100, "color": "#facc15"},
        {"periodo": 200, "color": "#a855f7"}
    ]

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

    return df

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
            st.warning("No se encontraron archivos .csv em la carpeta `./datos_bvc`.")
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
                
                st.dataframe(
                    df_display[columnas_mostrar], 
                    use_container_width=True, 
                    hide_index=True,
                    height=min(450, (len(df) + 1) * 38 + 12),
                    column_config={
                        "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                        "Recomendado": st.column_config.TextColumn("Recomendación", width="medium"),
                        "puntaje": st.column_config.ProgressColumn("Puntaje", format="%f pts", min_value=0, max_value=100, width="small"),
                        "precio": st.column_config.NumberColumn("Precio (Bs)", format="%.2f Bs", width="small"),
                        "precio_usd": st.column_config.NumberColumn("Precio (USD)", format="$%.4f", width="small"),
                        "target": st.column_config.NumberColumn("Target (Bs)", format="%.2f Bs", width="small"),
                        "upside": st.column_config.NumberColumn("Upside", format="+%.2f%%", width="small")
                    }
                )

            mostrar_tabla_interactiva(df_activos[df_activos['precio_usd'] < 1], "Acciones Menores a 1 USD", "tabla_menos_1")
            st.markdown("<br>", unsafe_allow_html=True)
            mostrar_tabla_interactiva(df_activos[df_activos['precio_usd'] >= 1], "Acciones Mayores o Iguales a 1 USD", "tabla_mas_1")

else:
    st.info("👈 Selecciona una fecha en el calendario de la barra lateral y presiona 'Analizar Carpeta'.")
