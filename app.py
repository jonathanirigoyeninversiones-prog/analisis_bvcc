import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
import subprocess
import sys
from datetime import datetime, date
import streamlit.components.v1 as components

# -------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------------------------
st.set_page_config(page_title="Analizador BVC - Sin Volumen", layout="wide")

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
        {
            "url": "https://api.exchangerate.host/latest?base=USD&symbols=VES",
            "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))
        },
        {
            "url": "https://open.er-api.com/v6/latest/USD",
            "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))
        },
        {
            "url": "https://api.exchangeratesapi.io/latest?base=USD&symbols=VES",
            "parse": lambda data: (data["rates"]["VES"], data.get("date", ""))
        }
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
        except Exception as e:
            continue
    
    return 0, ""

@st.cache_data(ttl=3600)
def get_dolar_con_cache():
    return obtener_dolar_oficial()

# -------------------------------------------------------------------
# 1. MAPEADOR DE SIMBOLOS BVC -> TRADINGVIEW
# -------------------------------------------------------------------
def obtener_simbolo_tradingview(nombre_empresa):
    # Diccionario para adaptar nombres de CSV a la nomenclatura exacta de TradingView en la BVC
    mapa_simbolos = {
        "BPV": "BVCV",
        "BVCC": "BVCC",
        "PCP.B": "PCP.B",
        "MVZ.A": "MVZ.A",
        "MVZ.B": "MVZ.B",
        "RST": "RST",
        "RST.B": "RST.B",
        "EFE": "EFE",
        "FNV": "FNV",
        "TDV.D": "TDV.D",
        "CRM.A": "CRM.A",
        "GPY": "GPY",
        "IVC": "IVC",
        "MPA": "MPA",
        "PGR": "PGR",
        "SVS": "SVS",
        "VCM": "VCM.B"
    }
    # Si la empresa está en el mapa usa el ticker exacto, si no, usa el nombre limpio agregando la bolsa
    ticker = mapa_simbolos.get(nombre_empresa.upper(), nombre_empresa.upper())
    return f"BVC:{ticker}"

# -------------------------------------------------------------------
# 2. GENERADOR DEL WIDGET OFICIAL DE TRADINGVIEW (HTML/JS)
# -------------------------------------------------------------------
def generar_widget_tradingview(simbolo_tv):
    html_code = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:100%;width:100%;">
      <div id="tradingview_bvc_chart" style="height:calc(100% - 32px);width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
      "autosize": true,
      "symbol": "{simbolo_tv}",
      "interval": "D",
      "timezone": "America/Caracas",
      "theme": "dark",
      "style": "1",
      "locale": "es",
      "toolbar_bg": "#f1f3f6",
      "enable_publishing": false,
      "hide_side_toolbar": false,
      "allow_symbol_change": true,
      "details": true,
      "hotlist": true,
      "calendar": true,
      "studies": [
        "STD;RSI",
        "STD;EMA",
        "STD;Bollinger_Bands"
      ],
      "container_id": "tradingview_bvc_chart"
    }}
      );
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    return html_code

# -------------------------------------------------------------------
# 3. CÁLCULO DE INDICADORES INTERNOS
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
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI_Anterior'] = df['RSI'].shift(1)

    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['BB_lower'] = df['SMA20'] - (2 * df['STD20'])
    df['BB_upper'] = df['SMA20'] + (2 * df['STD20'])

    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean()
    df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
    df['EMA100'] = df['Close'].ewm(span=100, adjust=False).mean()

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR14'] = true_range.rolling(14).mean()

    return df

# -------------------------------------------------------------------
# 4. ANALIZAR ARCHIVO
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
# 5. CONTROLADOR DEL MODAL FLOTANTE (INTERFACE NATIVA TRADINGVIEW)
# -------------------------------------------------------------------
if 'empresa_modal' not in st.session_state:
    st.session_state['empresa_modal'] = None

@st.dialog("📈 TradingView - Análisis Interactivo BVC", width="large")
def mostrar_modal_grafico(datos_empresa):
    simbolo_tv = obtener_simbolo_tradingview(datos_empresa['nombre'])
    widget_html = generar_widget_tradingview(simbolo_tv)
    components.html(widget_html, height=750, scrolling=False)

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
    st.title("📊 Analizador de Oportunidades BVC")
    st.markdown("**Estrategia sin volumen** - Basado únicamente en Precio, EMA, RSI y ATR.")

with col_dolar:
    with st.spinner("Cargando dólar..."):
        dolar_oficial, fecha_dolar = get_dolar_con_cache()
        if dolar_oficial > 0:
            st.markdown(f"""
            <div style="text-align: right; padding: 10px; background: transparent; border-radius: 12px; margin-top: 5px;">
                <p style="margin: 0; font-weight: 700; font-size: 1.2rem; color: #facc15; text-shadow: 0 0 8px rgba(250, 204, 21, 0.3);">
                    💵 Precio $ BCV: <strong>{fmt_bs(dolar_oficial)} Bs/USD</strong>
                </p>
                <p style="margin: 0; font-size: 0.7rem; color: #94a3b8;">
                    Actualizado: {fecha_dolar}
                </p>
            </div>
            """, unsafe_allow_html=True)

# --- FILTROS ---
st.markdown("""
**Filtros actuales (Sin Volumen):**  
1️⃣ **Tendencia (EMA 30 < EMA 60)** → +25 pts si está barata.  
2️⃣ **Distancia a EMA 60** → Hasta +40 pts si está muy por debajo.  
3️⃣ **Banda de Bollinger** → +15 pts si toca el suelo.  
4️⃣ **RSI (Nivel)** → Hasta +10 pts si está cerca de 30.  
5️⃣ **RSI (Pendiente)** → +10 pts si está subiendo y en sobreventa.  
6️⃣ **Potencial ATR** → +10 pts si subida >20%, +5 pts si >10%.  
7️⃣ **Bonus EMA 100** → +5 pts si está por debajo.
""")

carpeta = "./datos_bvc"

if btn_analizar:
    if not os.path.exists(carpeta):
        st.error("⚠️ La carpeta de datos aún no existe. Presiona 'Actualizar Historial BVC' para descargar el mercado.")
    else:
        archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
        if not archivos:
            st.warning("No hay datos descargados. Presiona 'Actualizar Historial BVC'.")
        else:
            resultados = []
            with st.spinner("Procesando todas las empresas del mercado..."):
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

        def mostrar_tabla(df, titulo):
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
            st.dataframe(df_display[columnas], use_container_width=True, hide_index=True)

        st.subheader(f"📈 Top Oportunidades - Referencia: {fecha_referencia.strftime('%Y-%m-%d')}")
        mostrar_tabla(df_menos_1, "🔽 Menos de 1 USD")
        mostrar_tabla(df_mas_1, "🔼 Mayor o igual a 1 USD")

        # --- SELECTOR DIRECTO PARA ABRIR MODAL TRADINGVIEW ---
        st.divider()
        st.subheader("🔍 Abrir Gráficos Interáctivos TradingView")
        
        lista_empresas = sorted([r['nombre'] for r in resultados])
        empresa_elegida = st.selectbox("Selecciona cualquier empresa para desplegar la interfaz completa de TradingView:", ["-- Selecciona una empresa --"] + lista_empresas)

        if empresa_elegida != "-- Selecciona una empresa --":
            datos_empresa = next((item for item in resultados if item["nombre"] == empresa_elegida), None)
            if datos_empresa:
                st.session_state['empresa_modal'] = datos_empresa

        # EJECUCIÓN DEL MODAL TRADINGVIEW
        if st.session_state['empresa_modal'] is not None:
            mostrar_modal_grafico(st.session_state['empresa_modal'])

else:
    st.info("👈 Presiona 'Analizar Mercado' en el menú lateral para cargar las tablas de oportunidades.")
