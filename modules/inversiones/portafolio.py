"""
modules/inversiones/portafolio.py
Vista del portafolio actual con precios en tiempo real.
Maneja múltiples monedas correctamente, incluyendo GBX.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from database.db import fetch_all
from utils.market_data import get_historial_por_fechas, normalizar_moneda, get_tipo_cambio_actual
import yfinance as yf


# ── Entry point ───────────────────────────────────────────────────────────────

def render() -> None:
    st.title("📋 Portafolio")
    st.divider()

    posiciones = fetch_all(
        """SELECT p.ticker, p.cantidad_total, p.costo_base_total,
                  p.primera_compra, a.nombre, a.sector, a.moneda
           FROM posiciones p
           LEFT JOIN activos a ON p.ticker = a.ticker
           WHERE p.cantidad_total > 0
           ORDER BY p.costo_base_total DESC"""
    )

    if not posiciones:
        st.info("No tenés posiciones abiertas. Registrá una compra en **Operaciones**.")
        return

    with st.spinner("Actualizando precios y tipos de cambio..."):
        datos = _enriquecer_posiciones(posiciones)

    if not datos:
        st.error("No se pudieron obtener precios actuales.")
        return

    df = pd.DataFrame(datos)

    # ── Métricas globales ─────────────────────────────────────────────────────
    _render_metricas_globales(df)
    st.divider()

    # ── Gráfico de la cartera (arriba) ────────────────────────────────────────
    _render_grafico_cartera(posiciones)
    st.divider()

    # ── Tabla de posiciones ───────────────────────────────────────────────────
    _render_tabla_posiciones(df)
    st.divider()

    # ── Gráficos de distribución ──────────────────────────────────────────────
    _render_graficos(df)


# ── Métricas globales ─────────────────────────────────────────────────────────

def _render_metricas_globales(df: pd.DataFrame) -> None:
    valor_total    = df["valor_usd"].sum()
    costo_total    = df["costo_base_total"].sum()
    ganancia_total = valor_total - costo_total
    rentabilidad   = (ganancia_total / costo_total * 100) if costo_total else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valor actual (USD)", f"${valor_total:,.2f}")
    col2.metric("Costo base (USD)", f"${costo_total:,.2f}")
    col3.metric(
        "Ganancia / Pérdida",
        f"${ganancia_total:+,.2f}",
        delta=f"{rentabilidad:+.2f}%",
        delta_color="normal" if ganancia_total >= 0 else "inverse",
    )
    col4.metric("Posiciones abiertas", len(df))


# ── Gráfico de la cartera ─────────────────────────────────────────────────────

def _render_grafico_cartera(posiciones: list[dict]) -> None:
    st.subheader("📈 Evolución de la cartera")

    fechas_compra = [p["primera_compra"] for p in posiciones if p["primera_compra"]]
    if not fechas_compra:
        st.info("No hay datos históricos suficientes.")
        return

    fecha_inicio = min(fechas_compra)

    ventanas = {
        "Desde inicio": fecha_inicio,
        "1 año":   (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
        "6 meses": (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d"),
        "3 meses": (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d"),
        "1 mes":   (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d"),
    }

    ventana_sel = st.radio(
        "Período",
        options=list(ventanas.keys()),
        index=0,
        horizontal=True,
        key="ventana_cartera",
    )

    fecha_desde = ventanas[ventana_sel]

    with st.spinner("Calculando evolución histórica..."):
        df_cartera = _calcular_valor_historico(posiciones, fecha_desde)

    if df_cartera is None or df_cartera.empty:
        st.warning("No hay datos históricos suficientes para este período.")
        return

    primer_valor  = df_cartera["valor_total"].iloc[0]
    ultimo_valor  = df_cartera["valor_total"].iloc[-1]
    variacion     = ultimo_valor - primer_valor
    variacion_pct = (variacion / primer_valor * 100) if primer_valor else 0
    color_linea   = "#26a69a" if variacion >= 0 else "#ef5350"
    simbolo       = "▲" if variacion >= 0 else "▼"

    def hex_a_rgba(hex_color, opacidad=0.15):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{opacidad})"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_cartera.index,
        y=df_cartera["valor_total"],
        mode="lines",
        name="Valor cartera",
        line=dict(color=color_linea, width=2),
        fill="tozeroy",
        fillcolor=hex_a_rgba(color_linea),
        hovertemplate="$%{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"Cartera — {simbolo} {abs(variacion_pct):.2f}% (${variacion:+,.2f} USD) en {ventana_sel}",
            font=dict(size=13, color="#aaaaaa"),
        ),
        xaxis=dict(showgrid=False, title="", showspikes=True,
                   spikecolor="#555555", spikethickness=1),
        yaxis=dict(
            showgrid=True, gridcolor="#333333", title="", tickprefix="$",
            range=[df_cartera["valor_total"].min() * 0.98,
                   df_cartera["valor_total"].max() * 1.02],
        ),
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=350,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)


def _calcular_valor_historico(posiciones: list[dict], fecha_desde: str) -> pd.DataFrame | None:
    """Calcula valor total del portafolio día a día en USD."""
    fecha_hasta = datetime.today().strftime("%Y-%m-%d")
    series = {}

    for p in posiciones:
        ticker   = p["ticker"]
        moneda   = p.get("moneda") or "USD"
        cantidad = p["cantidad_total"]
        _, factor = normalizar_moneda(moneda)

        try:
            df_hist = get_historial_por_fechas(ticker, fecha_desde, fecha_hasta)
            if df_hist is None or df_hist.empty:
                continue

            tc, _ = get_tipo_cambio_actual(moneda)

            # Precio en USD = precio_origen * factor_gbx * tc_base
            # tc ya incluye el factor para GBX (ver get_tipo_cambio_actual)
            serie = df_hist["Close"] * tc * cantidad
            series[ticker] = serie

        except Exception:
            continue

    if not series:
        return None

    df_combined = pd.DataFrame(series)
    # ffill compatible con pandas >= 2.0
    df_combined = df_combined.ffill().dropna()
    df_combined["valor_total"] = df_combined.sum(axis=1)

    return df_combined[["valor_total"]]


# ── Tabla de posiciones ───────────────────────────────────────────────────────

def _render_tabla_posiciones(df: pd.DataFrame) -> None:
    st.subheader("Posiciones abiertas")

    df_display = df[[
        "ticker", "nombre", "cantidad_total",
        "precio_compra_origen", "moneda",
        "precio_actual_origen", "valor_usd",
        "ganancia_usd", "rentabilidad_pct", "peso_pct"
    ]].copy()

    df_display.columns = [
        "Ticker", "Nombre", "Cantidad",
        "P. Compra (orig.)", "Moneda",
        "P. Actual (orig.)", "Valor USD",
        "G/P (USD)", "G/P (%)", "Peso %"
    ]

    def colorear_gp(row):
        base  = [""] * len(row)
        idx   = list(df_display.columns).index("G/P (USD)")
        color = "color: #26a69a" if row["G/P (USD)"] >= 0 else "color: #ef5350"
        base[idx]     = color
        base[idx + 1] = color
        return base

    st.dataframe(
        df_display.style
            .apply(colorear_gp, axis=1)
            .format({
                "Cantidad":          "{:,}",
                "P. Compra (orig.)": "{:,.4f}",
                "P. Actual (orig.)": "{:,.4f}",
                "Valor USD":         "${:,.2f}",
                "G/P (USD)":         "${:+,.2f}",
                "G/P (%)":           "{:+.2f}%",
                "Peso %":            "{:.1f}%",
            }),
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🏆 Top performers**")
        for _, row in df.nlargest(3, "rentabilidad_pct").iterrows():
            color = "green" if row["rentabilidad_pct"] >= 0 else "red"
            st.markdown(
                f"**{row['ticker']}** — :{color}[{row['rentabilidad_pct']:+.2f}%] "
                f"(${row['ganancia_usd']:+,.2f})"
            )
    with col2:
        st.markdown("**📉 Peores posiciones**")
        for _, row in df.nsmallest(3, "rentabilidad_pct").iterrows():
            color = "red" if row["rentabilidad_pct"] < 0 else "green"
            st.markdown(
                f"**{row['ticker']}** — :{color}[{row['rentabilidad_pct']:+.2f}%] "
                f"(${row['ganancia_usd']:+,.2f})"
            )


# ── Gráficos de distribución ──────────────────────────────────────────────────

def _render_graficos(df: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)
    with col1:
        _grafico_pie_activos(df)
    with col2:
        _grafico_sectores(df)


def _grafico_pie_activos(df: pd.DataFrame) -> None:
    st.subheader("Distribución por activo")
    fig = go.Figure(go.Pie(
        labels=df["ticker"],
        values=df["valor_usd"],
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
        height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _grafico_sectores(df: pd.DataFrame) -> None:
    st.subheader("Distribución por sector")
    df_sector = (
        df.groupby("sector", dropna=False)["valor_usd"]
        .sum().reset_index()
        .rename(columns={"sector": "Sector", "valor_usd": "Valor"})
    )
    df_sector["Sector"] = df_sector["Sector"].fillna("Sin clasificar")
    df_sector = df_sector.sort_values("Valor", ascending=True)
    df_sector["Pct"] = df_sector["Valor"] / df_sector["Valor"].sum() * 100

    colores = ["#26a69a", "#ef5350", "#42a5f5", "#ffca28",
               "#ab47bc", "#ff7043", "#66bb6a", "#26c6da"]

    fig = go.Figure(go.Bar(
        x=df_sector["Valor"],
        y=df_sector["Sector"],
        orientation="h",
        text=df_sector["Pct"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
        marker_color=colores[:len(df_sector)],
        hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(showgrid=False, title="", tickprefix="$"),
        yaxis=dict(showgrid=False, title=""),
        margin=dict(l=0, r=60, t=10, b=0),
        height=max(200, len(df_sector) * 60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Enriquecimiento de datos ──────────────────────────────────────────────────

def _enriquecer_posiciones(posiciones: list[dict]) -> list[dict]:
    """
    Para cada posición obtiene precio actual en moneda origen,
    convierte a USD y calcula G/P contra costo base (ya en USD).
    """
    datos = []

    for p in posiciones:
        ticker         = p["ticker"]
        moneda         = p.get("moneda") or "USD"
        cantidad       = int(p["cantidad_total"])
        costo_base_usd = p["costo_base_total"]

        _, factor = normalizar_moneda(moneda)

        try:
            t    = yf.Ticker(ticker)
            info = t.fast_info
            precio_actual_origen = getattr(info, "last_price", None)

            if precio_actual_origen is None:
                continue

            # Tipo de cambio actual a USD (ya incluye factor GBX)
            tc, _ = get_tipo_cambio_actual(moneda)

            # tc ya incluye el factor GBX (÷100 para GBp)
            # precio_actual_origen viene en moneda origen (GBX si es GBp)
            # Para GBX: precio_gbx * (gbpusd * 0.01) = precio_usd ✓
            precio_actual_usd = precio_actual_origen * tc
            valor_usd         = cantidad * precio_actual_usd
            ganancia_usd      = valor_usd - costo_base_usd
            rentabilidad      = (ganancia_usd / costo_base_usd * 100) if costo_base_usd else 0

            # Precio promedio de compra en moneda origen
            precio_compra_usd    = costo_base_usd / cantidad if cantidad else 0
            precio_compra_origen = precio_compra_usd / tc if tc else precio_compra_usd

            datos.append({
                "ticker":               ticker,
                "nombre":               p["nombre"] or ticker,
                "sector":               p["sector"] or "Sin clasificar",
                "moneda":               moneda,
                "cantidad_total":       cantidad,
                "costo_base_total":     costo_base_usd,
                "precio_compra_origen": precio_compra_origen,
                "precio_actual_origen": precio_actual_origen,
                "precio_actual_usd":    precio_actual_usd,
                "valor_usd":            valor_usd,
                "ganancia_usd":         ganancia_usd,
                "rentabilidad_pct":     rentabilidad,
                "peso_pct":             0,
            })

        except Exception as e:
            st.warning(f"⚠️ No se pudo obtener precio de {ticker}: {e}")
            continue

    valor_total = sum(d["valor_usd"] for d in datos)
    for d in datos:
        d["peso_pct"] = (d["valor_usd"] / valor_total * 100) if valor_total else 0

    return datos