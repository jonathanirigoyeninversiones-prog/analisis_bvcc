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

# --- Cabecera ---
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
            </div>
            """, unsafe_allow_html=True)

# --- Filtros ---
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
# 1. FUNCIÓN DE AGRUPACIÓN POR TEMPORALIDAD (RESAMPLING)
# -------------------------------------------------------------------
def cambiar_temporalidad(df, temporalidad):
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    if temporalidad == "1 Semana":
        df_resampled = df.resample('W').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
    elif temporalidad == "1 Mes":
        df_resampled = df.resample('ME').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
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
# 3. FUNCIÓN PARA DIBUJAR LA GRÁFICA TÉCNICA PROFESIONAL
# -------------------------------------------------------------------
def generar_grafico_tecnico(df, nombre_empresa, temporalidad):
    df_plot = df.tail(90).copy() # Mostrar últimos 90 registros para mejor definición visual

    # Creamos un diseño de 3 filas (Precio 60%, Volumen 15%, RSI 25%)
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        subplot_titles=(f'Gráfico Técnico ({temporalidad}) - {nombre_empresa}', 'Volumen de Transacciones', 'Fuerza Relativa RSI (14)'),
        row_width=[0.22, 0.15, 0.63]
    )

    # 1. VELAS JAPONESAS (Fila 1)
    fig.add_trace(go.Candlestick(
        x=df_plot['Date'], open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        name='Precio (Bs)',
        increasing_line_color='#22c55e', decreasing_line_color='#ef4444',
        increasing_fillcolor='#22c55e', decreasing_fillcolor='#ef4444'
    ), row=1, col=1)

    # Indicadores encima del precio
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['EMA30'], line=dict(color='#38bdf8', width=1.5), name='EMA 30'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['EMA60'], line=dict(color='#f43f5e', width=1.5), name='EMA 60'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_upper'], line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'), name='Bollinger Sup'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['BB_lower'], line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'), name='Bollinger Inf'), row=1, col=1)

    # 2. INDICADOR DE VOLUMEN CON COLORES DINÁMICOS (Fila 2)
    # Si Cierre >= Apertura -> Verde, si no -> Rojo
    colores_volumen = np.where(df_plot['Close'] >= df_plot['Open'], '#22c55e', '#ef4444')
    fig.add_trace(go.Bar(
        x=df_plot['Date'], y=df_plot['Volume'],
        marker_color=colores_volumen, name='Volumen',
        opacity=0.8
    ), row=2, col=1)

    # 3. GRÁFICO DEL RSI (Fila 3)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['RSI'], line=dict(color='#a855f7', width=2), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", row=3, col=1, line_color="#ef4444", line_width=1)
    fig.add_hline(y=30, line_dash="dash", row=3, col=1, line_color="#22c55e", line_width=1)

    # Estilo y diseño oscuro idéntico a TradingView
    fig.update_layout(
        height=750, 
        template='plotly_dark', 
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=50, b=30),
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(title_text="Precio (Bs)", row=1, col=1)
    fig.update_yaxes(title_text="Nominal", row=2, col=1)
    fig.update_yaxes(title_text="Nivel", range=[10, 90], row=3, col=1)
    
    return fig

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
# 5. INTERFAZ DE USUARIO
# -------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración")

carpeta = st.sidebar.text_input("📁 Ruta de la carpeta con tus CSV", value="./datos_bvc")

fecha_referencia = st.sidebar.date_input("📅 Fecha de referencia", value=date.today())

st.sidebar.divider()
st.sidebar.subheader("📥 Datos en la Nube")
if st.sidebar.button("🔄 Actualizar Historial BVC"):
    with st.spinner("Descargando datos históricos..."):
        try:
            subprocess.run([sys.executable, "descargador_cascada.py"], capture_output=True, text=True)
            st.sidebar.success("🎉 ¡Historial actualizado!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
st.sidebar.divider()

if st.sidebar.button("🔍 Analizar Carpeta"):
    if not os.path.exists(carpeta):
        st.error("⚠️ La ruta no existe. Primero presiona 'Actualizar Historial BVC'.")
    else:
        archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
        if not archivos:
            st.warning("La carpeta está vacía.")
        else:
            resultados = []
            with st.spinner("Procesando datos..."):
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

        # --- SECCIÓN DE GRÁFICO INTERACTIVO MULTI-TEMPORALIDAD ---
        st.divider()
        st.subheader("📈 Analizador Gráfico de Acción Multi-Temporalidad")
        
        col_selec, col_temp = st.columns([2, 1])
        
        with col_selec:
            lista_empresas = sorted([r['nombre'] for r in resultados])
            empresa_seleccionada = st.selectbox("Selecciona una empresa para analizar:", lista_empresas)
            
        with col_temp:
            temporalidad = st.radio("Temporalidad del gráfico:", ["1 Día", "1 Semana", "1 Mes"], horizontal=True)

        datos_empresa = next((item for item in resultados if item["nombre"] == empresa_seleccionada), None)

        if datos_empresa:
            df_convertido = cambiar_temporalidad(datos_empresa['df_original'], temporalidad)
            df_indicadores = calcular_indicadores(df_convertido)
            fig = generar_grafico_tecnico(df_indicadores, empresa_seleccionada, temporalidad)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Configura la ruta de tu carpeta, selecciona una fecha y presiona 'Analizar Carpeta'.")
