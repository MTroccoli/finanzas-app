"""
utils/market_data.py
Wrapper centralizado de yfinance.
Todos los módulos de inversiones usan este archivo para obtener datos de mercado.
Nunca llaman a yfinance directamente.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache
import streamlit as st


# ── Ventanas temporales disponibles ──────────────────────────────────────────

VENTANAS = {
    "1D":  {"period": "1d",  "interval": "5m"},
    "1W":  {"period": "5d",  "interval": "30m"},
    "1M":  {"period": "1mo", "interval": "1d"},
    "3M":  {"period": "3mo", "interval": "1d"},
    "6M":  {"period": "6mo", "interval": "1d"},
    "1Y":  {"period": "1y",  "interval": "1wk"},
    "YTD": {"period": "ytd", "interval": "1d"},
    "MAX": {"period": "max", "interval": "1mo"},
}


# ── Precio actual ─────────────────────────────────────────────────────────────

def get_precio_actual(ticker: str) -> dict | None:
    """
    Devuelve el precio actual y variación diaria de un ticker.

    Retorna dict con:
        ticker, nombre, precio, variacion_dia, variacion_dia_pct,
        volumen, market_cap, pe_ratio, dividendo_yield,
        semana_52_max, semana_52_min, moneda
    Retorna None si el ticker no existe o hay error.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        # Precio: fast_info es más confiable y rápido
        precio = info.get("currentPrice") or info.get("regularMarketPrice")
        if precio is None:
            return None

        cierre_anterior = info.get("previousClose", precio)
        variacion       = precio - cierre_anterior
        variacion_pct   = (variacion / cierre_anterior * 100) if cierre_anterior else 0

        return {
            "ticker":           ticker.upper(),
            "nombre":           info.get("longName") or info.get("shortName", ticker),
            "precio":           precio,
            "variacion_dia":    round(variacion, 4),
            "variacion_dia_pct":round(variacion_pct, 2),
            "volumen":          info.get("volume"),
            "market_cap":       info.get("marketCap"),
            "pe_ratio":         info.get("trailingPE"),
            "dividendo_yield":  info.get("dividendYield"),
            "semana_52_max":    info.get("fiftyTwoWeekHigh"),
            "semana_52_min":    info.get("fiftyTwoWeekLow"),
            "moneda":           info.get("currency", "USD"),
            "tipo":             info.get("quoteType", "").lower(),  # equity, etf, etc.
            "sector":           info.get("sector"),
            "industria":        info.get("industry"),
        }

    except Exception as e:
        st.warning(f"⚠️ No se pudo obtener precio de {ticker}: {e}")
        return None


# ── Precios de múltiples tickers a la vez ────────────────────────────────────

def get_precios_multiples(tickers: list[str]) -> dict[str, float]:
    """
    Devuelve {ticker: precio_actual} para una lista de tickers.
    Más eficiente que llamar get_precio_actual() en un loop.
    """
    if not tickers:
        return {}
    try:
        if len(tickers) == 1:
            # Para un solo ticker usamos get_precio_actual() que es más confiable
            ticker = tickers[0].upper()
            datos  = get_precio_actual(ticker)
            return {ticker: datos["precio"]} if datos else {}

        data  = yf.download(
            tickers,
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            return {}

        close   = data["Close"]
        precios = {}

        for ticker in tickers:
            t = ticker.upper()
            if t in close.columns:
                # Tomar el último valor no-NaN
                serie = close[t].dropna()
                if not serie.empty:
                    precios[t] = float(serie.iloc[-1])

        return precios

    except Exception as e:
        st.warning(f"⚠️ Error al obtener precios múltiples: {e}")
        return {}


# ── Historial de precios ──────────────────────────────────────────────────────

def get_historial(ticker: str, ventana: str = "1M") -> pd.DataFrame | None:
    """
    Devuelve DataFrame con el historial de precios para la ventana indicada.

    Ventanas válidas: 1D | 1W | 1M | 3M | 6M | 1Y | YTD | MAX

    Columnas del DataFrame: Open, High, Low, Close, Volume
    Index: DatetimeIndex
    """
    if ventana not in VENTANAS:
        ventana = "1M"

    config = VENTANAS[ventana]

    try:
        t = yf.Ticker(ticker)
        df = t.history(
            period=config["period"],
            interval=config["interval"],
            auto_adjust=True,
        )

        if df.empty:
            return None

        # Limpiar columnas innecesarias
        cols_mantener = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in cols_mantener if c in df.columns]]
        df.index = pd.to_datetime(df.index)

        return df

    except Exception as e:
        st.warning(f"⚠️ Error al obtener historial de {ticker}: {e}")
        return None


# ── Historial por rango de fechas ─────────────────────────────────────────────

def get_historial_por_fechas(
    ticker: str,
    fecha_inicio: str,
    fecha_fin: str | None = None,
) -> pd.DataFrame | None:
    """
    Devuelve historial de precios entre dos fechas específicas.
    Útil para calcular rentabilidad de una posición desde la fecha de compra.

    Args:
        ticker:       Símbolo del activo
        fecha_inicio: Fecha de inicio en formato YYYY-MM-DD
        fecha_fin:    Fecha de fin (default: hoy)

    Retorna DataFrame con columnas Open, High, Low, Close, Volume
    """
    try:
        if fecha_fin is None:
            fecha_fin = datetime.today().strftime("%Y-%m-%d")

        t  = yf.Ticker(ticker)
        df = t.history(start=fecha_inicio, end=fecha_fin, auto_adjust=True)

        if df.empty:
            return None

        cols_mantener = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in cols_mantener if c in df.columns]]
        df.index = pd.to_datetime(df.index)

        return df

    except Exception as e:
        st.warning(f"⚠️ Error al obtener historial de {ticker}: {e}")
        return None


# ── Precio en una fecha específica ────────────────────────────────────────────

def get_precio_en_fecha(ticker: str, fecha: str) -> float | None:
    """
    Devuelve el precio de cierre de un ticker en una fecha específica.
    Útil para calcular el valor histórico del portafolio.

    Args:
        ticker: Símbolo del activo
        fecha:  Fecha en formato YYYY-MM-DD
    """
    try:
        fecha_dt  = datetime.strptime(fecha, "%Y-%m-%d")
        fecha_fin = (fecha_dt + timedelta(days=5)).strftime("%Y-%m-%d")

        t  = yf.Ticker(ticker)
        df = t.history(start=fecha, end=fecha_fin, auto_adjust=True)

        if df.empty:
            return None

        return float(df["Close"].iloc[0])

    except Exception as e:
        st.warning(f"⚠️ Error al obtener precio de {ticker} en {fecha}: {e}")
        return None


# ── Búsqueda de tickers ───────────────────────────────────────────────────────

def buscar_ticker(query: str) -> list[dict]:
    """
    Busca tickers por nombre o símbolo.
    Retorna lista de dicts con ticker, nombre, tipo, exchange.

    Nota: yfinance no tiene búsqueda nativa. Usamos el endpoint
    de búsqueda de Yahoo Finance directamente.
    """
    import requests

    if not query or len(query) < 1:
        return []

    try:
        url    = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q":            query,
            "lang":         "en-US",
            "region":       "US",
            "quotesCount":  8,
            "newsCount":    0,
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp    = requests.get(url, params=params, headers=headers, timeout=5)
        data    = resp.json()

        resultados = []
        for item in data.get("quotes", []):
            if item.get("symbol"):
                resultados.append({
                    "ticker":   item["symbol"],
                    "nombre":   item.get("longname") or item.get("shortname", ""),
                    "tipo":     item.get("quoteType", "").lower(),
                    "exchange": item.get("exchange", ""),
                })

        return resultados

    except Exception as e:
        st.warning(f"⚠️ Error en búsqueda: {e}")
        return []


def normalizar_moneda(moneda: str) -> tuple[str, float]:
    """GBX/GBp → GBP con factor 0.01. Resto sin cambio."""
    if moneda in ("GBX", "GBx", "GBp"):
        return "GBP", 0.01
    return moneda.upper(), 1.0


def get_tipo_cambio_actual(moneda: str) -> tuple[float, str]:
    """Devuelve (tipo_cambio_a_usd, moneda_normalizada). Maneja GBX."""
    import yfinance as yf
    moneda_norm, factor = normalizar_moneda(moneda)
    if moneda_norm == "USD":
        return 1.0, "USD"
    try:
        par    = f"{moneda_norm}USD=X"
        ticker = yf.Ticker(par)
        info   = ticker.fast_info
        precio = getattr(info, "last_price", None)
        if precio:
            return float(precio) * factor, moneda_norm
    except Exception:
        pass
    return factor, moneda_norm

# ── Información básica del activo ─────────────────────────────────────────────

@st.cache_data(ttl=3600)  # Cache de 1 hora para datos que cambian poco
def get_info_activo(ticker: str) -> dict | None:
    """
    Devuelve información estática del activo (nombre, sector, tipo).
    Se cachea 1 hora porque no cambia frecuentemente.
    """
    try:
        t    = yf.Ticker(ticker)
        info = t.info

        if not info or "symbol" not in info:
            return None

        return {
            "ticker":    ticker.upper(),
            "nombre":    info.get("longName") or info.get("shortName", ticker),
            "tipo":      info.get("quoteType", "").lower(),
            "sector":    info.get("sector"),
            "industria": info.get("industry"),
            "pais":      info.get("country"),
            "moneda":    info.get("currency", "USD"),
        }

    except Exception:
        return None


# ── Utilidades de formato ─────────────────────────────────────────────────────

def formatear_numero(valor: float | None, decimales: int = 2, prefijo: str = "") -> str:
    """Formatea un número para mostrar en UI. Ej: 1234567 → $1.23M"""
    if valor is None:
        return "N/D"
    if abs(valor) >= 1_000_000_000:
        return f"{prefijo}{valor/1_000_000_000:.{decimales}f}B"
    if abs(valor) >= 1_000_000:
        return f"{prefijo}{valor/1_000_000:.{decimales}f}M"
    if abs(valor) >= 1_000:
        return f"{prefijo}{valor/1_000:.{decimales}f}K"
    return f"{prefijo}{valor:.{decimales}f}"


def formatear_variacion(valor: float | None) -> str:
    """Devuelve string con ▲/▼ y color para mostrar variación."""
    if valor is None:
        return "N/D"
    simbolo = "▲" if valor >= 0 else "▼"
    return f"{simbolo} {abs(valor):.2f}%"
