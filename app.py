import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
import subprocess
import sys
from datetime import datetime, date

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

# --- AHORA SE ACTUALIZA CADA HORA (3600 SEGUNDOS) ---
@st.cache_data(ttl=3600)
def get_dolar_con_cache():
    return obtener_dolar_oficial()

# --- Cabecera con Título a la izquierda y Dólar a la derecha ---
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
        else:
            st.markdown("""
            <div style="text-align: right; padding: 10px; background: transparent; border-radius: 12px; margin-top: 5px;">
                <p style="margin: 0; font-weight: 600; font-size: 1.0rem; color: #facc15; text-shadow: 0 0 8px rgba(250, 204, 21, 0.3);">
                    ⚠️ Precio $ BCV: No disponible
                </p>
                <p style="margin: 0; font-size: 0.7rem; color: #94a3b8;">
                    Intente recargar la página o verifique conexión
                </p>
            </div>
            """, unsafe_allow_html=True)

# --- Mostrar los filtros (debajo de la cabecera) ---
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

# -------------------------------------------------------------------
# 1. FUNCIÓN QUE CALCULA TODOS LOS INDICADORES TÉCNICOS
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
# 2. FUNCIÓN QUE ANALIZA CADA ARCHIVO (SIN VOLUMEN)
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
            return {
                'nombre': os.path.basename(ruta_archivo).replace('.csv', ''),
                'estado': '❌ Sin Datos',
                'puntaje': 0,
                'precio': 0,
                'target': 0,
                'upside': 0,
                'rsi': 0,
                'rsi_ayer': 0,
                'ema30': 0,
                'ema60': 0,
                'fecha_ultimo': fecha_referencia.strftime('%Y-%m-%d'),
            }

        df = df.sort_values('Date').reset_index(drop=True)

        df_con_volumen = df[df['Volume'] > 0]
        if df_con_volumen.empty:
            ultimo = df.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')
        else:
            ultimo = df_con_volumen.iloc[-1]
            fecha_ultimo_operado = ultimo['Date'].strftime('%Y-%m-%d')

        df = calcular_indicadores(df)

        ultimo_fila = df[df['Date'] == ultimo['Date']]
        if ultimo_fila.empty:
            ultimo = df.iloc[-1]
        else:
            ultimo = ultimo_fila.iloc[-1]

        puntaje = 0

        if ultimo['EMA30'] < ultimo['EMA60']:
            puntaje += 25

        if not pd.isna(ultimo['EMA60']) and ultimo['EMA60'] > 0:
            distancia_ema = ((ultimo['EMA60'] - ultimo['Close']) / ultimo['EMA60']) * 100
            if distancia_ema > 0:
                pts_ema = min(distancia_ema * 1.6, 40)
                puntaje += pts_ema

        if not pd.isna(ultimo['BB_lower']) and ultimo['Close'] < ultimo['BB_lower']:
            puntaje += 15

        rsi_hoy = ultimo['RSI']
        rsi_ayer = ultimo['RSI_Anterior']
        if not pd.isna(rsi_hoy):
            distancia_al_30 = abs(rsi_hoy - 30)
            pts_nivel = max(0, 10 - distancia_al_30)
            puntaje += pts_nivel

        if not pd.isna(rsi_hoy) and not pd.isna(rsi_ayer):
            if rsi_hoy > rsi_ayer and rsi_hoy < 40:
                puntaje += 10

        if not pd.isna(ultimo['ATR14']) and ultimo['ATR14'] > 0:
            target = ultimo['Close'] + (1.5 * ultimo['ATR14'])
            upside = ((target - ultimo['Close']) / ultimo['Close']) * 100
            if upside > 20:
                puntaje += 10
            elif upside > 10:
                puntaje += 5
        else:
            target = 0
            upside = 0

        if 'EMA100' in ultimo and not pd.isna(ultimo['EMA100']) and ultimo['Close'] < ultimo['EMA100']:
            puntaje += 5

        puntaje = min(puntaje, 100)

        if puntaje >= 60 and ultimo['EMA30'] < ultimo['EMA60']:
            estado = '✅ COMPRA'
        elif puntaje >= 35:
            estado = '🔍 SEGUIMIENTO'
        else:
            estado = '⏸️ ESPERAR'

        return {
            'nombre': os.path.basename(ruta_archivo).replace('.csv', ''),
            'estado': estado,
            'puntaje': round(puntaje, 1),
            'precio': float(ultimo['Close']),
            'target': float(target),
            'upside': float(upside),
            'rsi': round(rsi_hoy, 2) if not pd.isna(rsi_hoy) else 0,
            'rsi_ayer': round(rsi_ayer, 2) if not pd.isna(rsi_ayer) else 0,
            'ema30': float(ultimo['EMA30']) if not pd.isna(ultimo['EMA30']) else 0,
            'ema60': float(ultimo['EMA60']) if not pd.isna(ultimo['EMA60']) else 0,
            'fecha_ultimo': fecha_ultimo_operado,
        }

    except Exception as e:
        return {
            'nombre': os.path.basename(ruta_archivo).replace('.csv', ''),
            'estado': '⚠️ ERROR',
            'puntaje': 0,
            'precio': 0,
            'target': 0,
            'upside': 0,
            'rsi': 0,
            'rsi_ayer': 0,
            'ema30': 0,
            'ema60': 0,
            'fecha_ultimo': 'Error',
        }

# -------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO (CON CALENDARIO Y DOS TABLAS)
# -------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración")

carpeta = st.sidebar.text_input(
    "📁 Ruta de la carpeta con tus CSV",
    value="./datos_bvc"
)

fecha_referencia = st.sidebar.date_input(
    "📅 Fecha de referencia (viaje en el tiempo)",
    value=date.today(),
    help="La app buscará el último dato disponible en o antes de esta fecha."
)

# --- BOTÓN DE ACTUALIZACIÓN ---
st.sidebar.divider()
st.sidebar.subheader("📥 Datos en la Nube")
if st.sidebar.button("🔄 Actualizar Historial BVC", help="Descarga los datos más recientes desde internet"):
    with st.spinner("Descargando precios históricos de la BVC... Esto puede tomar un minuto."):
        try:
            resultado = subprocess.run([sys.executable, "descargador_cascada.py"], capture_output=True, text=True)
            st.sidebar.success("🎉 ¡Historial descargado con éxito!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error al descargar: {e}")
st.sidebar.divider()

if st.sidebar.button("🔍 Analizar Carpeta"):
    if not os.path.exists(carpeta):
        st.error("⚠️ La ruta no existe. Primero presiona el botón 'Actualizar Historial BVC' de arriba.")
    else:
        archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
        if not archivos:
            st.warning("La carpeta está vacía. Presiona 'Actualizar Historial BVC'.")
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
                df_resultados = pd.DataFrame(resultados)
                
                df_activos = df_resultados[~df_resultados['estado'].isin(['❌ Sin Datos', '⚠️ ERROR'])].copy()
                df_activos = df_activos.sort_values('puntaje', ascending=False)

                dolar, _ = get_dolar_con_cache()

                if dolar == 0:
                    st.warning("⚠️ No se pudo obtener el dólar oficial. No se pueden crear las tablas por precio en USD.")
                else:
                    df_activos['precio_usd'] = df_activos['precio'] / dolar

                    df_menos_1 = df_activos[df_activos['precio_usd'] < 1].copy()
                    df_mas_1 = df_activos[df_activos['precio_usd'] >= 1].copy()

                    def mostrar_tabla(df, titulo):
                        if df.empty:
                            st.info(f"📭 No hay acciones en '{titulo}'")
                            return
                        
                        df_display = df.copy()
                        df_display = df_display.rename(columns={'estado': 'Recomendado'})
                        for col in ['precio', 'target', 'ema30', 'ema60']:
                            df_display[col] = df_display[col].apply(fmt_bs)
                        df_display['precio_usd'] = df_display['precio_usd'].apply(lambda x: f"{x:.4f}")
                        df_display['upside'] = df_display['upside'].apply(lambda x: f"{x:.2f}%")
                        df_display['rsi'] = df_display['rsi'].apply(lambda x: f"{x:.2f}")
                        df_display['rsi_ayer'] = df_display['rsi_ayer'].apply(lambda x: f"{x:.2f}")

                        columnas_mostrar = [
                            'nombre', 'fecha_ultimo', 'Recomendado', 'puntaje', 'precio', 'precio_usd', 'target', 'upside',
                            'rsi', 'rsi_ayer', 'ema30', 'ema60'
                        ]
                        st.subheader(f"📊 {titulo} ({len(df)} acciones)")
                        st.dataframe(
                            df_display[columnas_mostrar],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "puntaje": st.column_config.ProgressColumn("Puntaje", format="%d", min_value=0, max_value=100),
                                "precio": st.column_config.TextColumn("Precio (Bs)"),
                                "precio_usd": st.column_config.TextColumn("Precio (USD)"),
                                "target": st.column_config.TextColumn("Target (Bs)"),
                                "upside": st.column_config.TextColumn("Upside %"),
                                "rsi": st.column_config.TextColumn("RSI Hoy"),
                                "rsi_ayer": st.column_config.TextColumn("RSI Ayer"),
                                "ema30": st.column_config.TextColumn("EMA 30 (Bs)"),
                                "ema60": st.column_config.TextColumn("EMA 60 (Bs)"),
                                "fecha_ultimo": st.column_config.TextColumn("Último Día Operado"),
                            }
                        )

                    st.subheader(f"📈 Top Oportunidades - Referencia: {fecha_referencia.strftime('%Y-%m-%d')}")
                    mostrar_tabla(df_menos_1, "🔽 Menos de 1 USD")
                    mostrar_tabla(df_mas_1, "🔼 Mayor o igual a 1 USD")

                with st.expander("ℹ️ Ver archivos sin datos o con error"):
                    df_error = df_resultados[df_resultados['estado'].isin(['❌ Sin Datos', '⚠️ ERROR'])].copy()
                    df_error = df_error.rename(columns={'estado': 'Recomendado'})
                    st.dataframe(df_error)

else:
    st.info("👈 Configura la ruta de tu carpeta, selecciona una fecha y presiona 'Analizar Carpeta'.")
