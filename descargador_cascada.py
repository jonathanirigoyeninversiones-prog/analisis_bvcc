import os
import time
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime
from tradingview_screener import Query, col

# ============================================================
# CONFIGURACIÓN
# ============================================================
ALPHA_VANTAGE_KEY = ""  # Pon tu API Key de Alpha Vantage si quieres

# ============================================================
# LISTA DE 41 EMPRESAS (SOLO SÍMBOLOS)
# ============================================================
SIMBOLOS = [
    "ABCA", "BNC", "BPV", "BVCC", "BVL", "2CIE", "CCR", "CCP.B", "CRM.A",
    "CGQ", "DOM", "EFE", "ENV", "FNC", "FNV",
    "GZL", "GMC.B", "ICP.B", "IVC.A", "IVC.B", "MPA", "MVZ.A", "MVZ.B",
    "PGR", "PTN", "PER", "PCP.B", "RST", "RST.B", "SVS", "TPG", "TDV.D",
    "PIV.B", "MTC.B", "ARC.A", "ARC.B", "ALZ.B", "FFV.B", "GZL.B",
    "IMP.B", "RFM", "VNA.B"
]

# ============================================================
# MAPEO A YAHOO FINANCE
# ============================================================
MAPEO_YAHOO = {
    "ABCA": ["ABC-A.CR", "ABCA.CR", "ABCA"],
    "BNC": ["BNC.CR", "BNC"],
    "BPV": ["BPV.CR", "BPV"],
    "BVCC": ["BVCC.CR", "BVCC"],
    "BVL": ["BVL.CR", "BVL"],
    "2CIE": ["2CIE.CR", "2CIE", "CIE.CR", "CIE"],
    "CCR": ["CCR.CR", "CCR"],
    "CCP.B": ["CCP-B.CR", "CCP-B", "CCPB.CR"],
    "CRM.A": ["CRM-A.CR", "CRM-A", "CRMA.CR"],
    "CGQ": ["CGQ.CR", "CGQ"],
    "DOM": ["DOM.CR", "DOM"],
    "EFE": ["EFE.CR", "EFE"],
    "ENV": ["ENV.CR", "ENV"],
    "FNC": ["FNC.CR", "FNC"],
    "FNV": ["FNV.CR", "FNV"],
    "GZL": ["GZL.CR", "GZL"],
    "GMC.B": ["GMC-B.CR", "GMC-B", "GMCB.CR"],
    "ICP.B": ["ICP-B.CR", "ICP-B", "ICPB.CR"],
    "IVC.A": ["IVC-A.CR", "IVC-A", "IVCA.CR"],
    "IVC.B": ["IVC-B.CR", "IVC-B", "IVCB.CR"],
    "MPA": ["MPA.CR", "MPA"],
    "MVZ.A": ["MVZ-A.CR", "MVZ-A", "MVZA.CR"],
    "MVZ.B": ["MVZ-B.CR", "MVZ-B", "MVZB.CR"],
    "PGR": ["PGR.CR", "PGR"],
    "PTN": ["PTN.CR", "PTN"],
    "PER": ["PER.CR", "PER"],
    "PCP.B": ["PCP-B.CR", "PCP-B", "PCPB.CR"],
    "RST": ["RST.CR", "RST"],
    "RST.B": ["RST-B.CR", "RST-B", "RSTB.CR"],
    "SVS": ["SVS.CR", "SVS"],
    "TPG": ["TPG.CR", "TPG"],
    "TDV.D": ["TDV-D.CR", "TDV-D", "TDVD.CR"],
    "PIV.B": ["PIV-B.CR", "PIV-B", "PIVB.CR"],
    "MTC.B": ["MTC-B.CR", "MTC-B", "MTCB.CR"],
    "ARC.A": ["ARC-A.CR", "ARC-A", "ARCA.CR"],
    "ARC.B": ["ARC-B.CR", "ARC-B", "ARCB.CR"],
    "ALZ.B": ["ALZ-B.CR", "ALZ-B", "ALZB.CR"],
    "FFV.B": ["FFV-B.CR", "FFV-B", "FFVB.CR"],
    "GZL.B": ["GZL-B.CR", "GZL-B", "GZLB.CR"],
    "IMP.B": ["IMP-B.CR", "IMP-B", "IMPB.CR"],
    "RFM": ["RFM.CR", "RFM"],
    "VNA.B": ["VNA-B.CR", "VNA-B", "VNAB.CR"],
}

# ============================================================
# FUNCIONES DE DESCARGA
# ============================================================
def descargar_tradingview_screener(nombre):
    print(f"   🔍 TradingView: {nombre}...", end=" ")
    try:
        data = (Query()
                .select('symbol', 'close', 'volume', 'market_cap_basic')
                .where(col('symbol') == nombre)
                .where(col('exchange') == 'BVCV')
                .get_scanner_data())
        if not isinstance(data, pd.DataFrame) or data.empty:
            print("⚠️ Sin datos")
            return None
        row = data.iloc[0]
        df = pd.DataFrame({
            'Date': [datetime.now().strftime('%Y-%m-%d')],
            'Open': [float(row['close'])],
            'High': [float(row['close'])],
            'Low': [float(row['close'])],
            'Close': [float(row['close'])],
            'Volume': [float(row['volume']) if 'volume' in data.columns else 0]
        })
        print(f"✅ 1 registro")
        return df
    except Exception as e:
        print(f"❌ Error")
        return None

def descargar_alphavantage(nombre):
    if not ALPHA_VANTAGE_KEY:
        return None
    print(f"   🔍 Alpha Vantage: {nombre}...", end=" ")
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={nombre}&apikey={ALPHA_VANTAGE_KEY}&outputsize=full&datatype=csv"
        df = pd.read_csv(url)
        if df.empty:
            print("⚠️ Sin datos")
            return None
        df = df.rename(columns={'timestamp': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
        df['Date'] = pd.to_datetime(df['Date'])
        print(f"✅ {len(df)} registros")
        return df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        print(f"❌ Error")
        return None

def descargar_yahoo(nombre):
    variantes = MAPEO_YAHOO.get(nombre, [f"{nombre}.CR", nombre])
    for simbolo in variantes:
        print(f"   🔍 Yahoo: {simbolo}...", end=" ")
        try:
            df = yf.download(simbolo, period="max", progress=False)
            if df.empty:
                print("⚠️ Sin datos")
                continue
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date'])
            print(f"✅ {len(df)} registros")
            return df
        except Exception as e:
            print(f"❌ Error")
            continue
    return None

# ============================================================
# DESCARGA PRINCIPAL (SIN REPORTES)
# ============================================================
def descargar_empresa(nombre):
    print(f"\n🔍 {nombre}...")
    fuentes = [
        ("TradingView", descargar_tradingview_screener),
        ("Alpha Vantage", descargar_alphavantage),
        ("Yahoo Finance", descargar_yahoo),
    ]
    for nombre_fuente, func in fuentes:
        try:
            df = func(nombre)
            if df is not None and not df.empty:
                archivo = f"datos_bvc/{nombre}.csv"
                df.to_csv(archivo, index=False)
                print(f"   ✅ Guardado en {archivo}")
                return True
        except Exception as e:
            print(f"   ❌ {nombre_fuente}")
        time.sleep(0.3)
    print(f"   ❌ No se encontraron datos para {nombre}")
    return False

# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================
if __name__ == "__main__":
    os.makedirs("datos_bvc", exist_ok=True)
    print("=" * 70)
    print("📥 DESCARGADOR EN CASCADA - BVC (41 empresas)")
    print("   🔹 PRIORIDAD: TradingView → Alpha Vantage → Yahoo")
    print("=" * 70)

    for nombre in SIMBOLOS:
        descargar_empresa(nombre)

    print("\n" + "=" * 70)
    print("✅ DESCARGA COMPLETADA")
    print("📂 Carpeta: datos_bvc/")
    print("=" * 70)