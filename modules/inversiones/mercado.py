"""
modules/inversiones/mercado.py
Vista de mercado en tiempo real.
Permite buscar cualquier ticker, ver precio actual y gráfico histórico.
"""

import streamlit as st
import plotly.graph_objects as go
from utils.market_data import (
    buscar_ticker,
    get_precio_actual,
    get_historial,
    formatear_numero,
    VENTANAS,
)


# ── Entry point ───────────────────────────────────────────────────────────────

def render() -> None:
    st.title("🌐 Mercado en tiempo real")
    st.divider()

    # Buscador principal
    _render_buscador()


# ── Buscador ──────────────────────────────────────────────────────────────────

def _render_buscador() -> None:
    """Buscador de ticker con autocompletado."""

    col_search, col_btn = st.columns([4, 1])

    with col_search:
        query = st.text_input(
            "Buscar activo",
            placeholder="Ej: AAPL, SPY, Bitcoin...",
            label_visibility="collapsed",
        )

    with col_btn:
        buscar = st.button("🔍 Buscar", use_container_width=True)

    # Si hay query, mostrar sugerencias o ir directo al ticker
    if query:
        # Intentar como ticker directo primero
        if buscar or len(query) >= 2:
            resultados = buscar_ticker(query)

            if not resultados:
                st.warning("No se encontraron resultados. Verificá el ticker.")
                return

            # Si el query coincide exactamente con un ticker, ir directo
            tickers_exactos = [r for r in resultados if r["ticker"].upper() == query.upper()]
            if tickers_exactos:
                _render_detalle_activo(tickers_exactos[0]["ticker"])
                return

            # Si hay múltiples resultados, mostrar lista para elegir
            st.markdown("**Resultados de búsqueda:**")
            for r in resultados:
                tipo_badge = _badge_tipo(r["tipo"])
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**{r['ticker']}** — {r['nombre']} {tipo_badge}  \n`{r['exchange']}`")
                with col2:
                    if st.button("Ver", key=f"ver_{r['ticker']}"):
                        st.session_state["ticker_seleccionado"] = r["ticker"]
                        st.rerun()

    # Si hay un ticker seleccionado en session_state, mostrarlo
    if "ticker_seleccionado" in st.session_state:
        st.divider()
        _render_detalle_activo(st.session_state["ticker_seleccionado"])


# ── Detalle del activo ────────────────────────────────────────────────────────

def _render_detalle_activo(ticker: str) -> None:
    """Muestra precio actual, métricas clave y gráfico histórico."""

    with st.spinner(f"Cargando datos de {ticker}..."):
        datos = get_precio_actual(ticker)

    if datos is None:
        st.error(f"No se pudieron obtener datos para **{ticker}**.")
        return

    # ── Encabezado ────────────────────────────────────────────────────────────
    col_titulo, col_compra = st.columns([6, 1])
    with col_titulo:
        st.subheader(f"{datos['ticker']} — {datos['nombre']}")
        if datos.get("sector"):
            st.caption(f"{datos['sector']} · {datos.get('industria', '')}")

    with col_compra:
        if st.button("➕ Registrar compra", type="primary", use_container_width=True):
            st.session_state["compra_ticker"] = ticker
            st.session_state["compra_precio"] = datos["precio"]
            # Redirigir a operaciones (el usuario navega desde el sidebar)
            st.info("Andá a **Operaciones** en el sidebar para registrar la compra.")

    # ── Precio y variación diaria ─────────────────────────────────────────────
    variacion     = datos["variacion_dia"]
    variacion_pct = datos["variacion_dia_pct"]
    color_var     = "green" if variacion >= 0 else "red"
    simbolo       = "▲" if variacion >= 0 else "▼"

    col_precio, col_var, col_var_pct = st.columns(3)

    with col_precio:
        st.metric(
            label="Precio actual",
            value=f"${datos['precio']:,.2f}",
        )
    with col_var:
        st.metric(
            label="Variación día ($)",
            value=f"${abs(variacion):,.2f}",
            delta=f"{simbolo} {abs(variacion):,.2f}",
            delta_color="normal" if variacion >= 0 else "inverse",
        )
    with col_var_pct:
        st.metric(
            label="Variación día (%)",
            value=f"{abs(variacion_pct):.2f}%",
            delta=f"{simbolo} {abs(variacion_pct):.2f}%",
            delta_color="normal" if variacion_pct >= 0 else "inverse",
        )

    st.divider()

    # ── Gráfico histórico ─────────────────────────────────────────────────────
    _render_grafico(ticker, datos["nombre"])

    st.divider()

    # ── Datos clave ───────────────────────────────────────────────────────────
    _render_datos_clave(datos)


# ── Gráfico ───────────────────────────────────────────────────────────────────

def _render_grafico(ticker: str, nombre: str) -> None:
    """Gráfico de precio histórico con selector de ventana temporal."""

    # Selector de ventana
    ventanas_opciones = list(VENTANAS.keys())
    ventana = st.radio(
        "Período",
        options=ventanas_opciones,
        index=2,            # Default: 1M
        horizontal=True,
        key=f"ventana_{ticker}",
    )

    with st.spinner("Cargando gráfico..."):
        df = get_historial(ticker, ventana)

    if df is None or df.empty:
        st.warning("No hay datos históricos disponibles para este período.")
        return

    # Determinar color según variación en el período
    primer_precio = float(df["Close"].iloc[0])
    ultimo_precio = float(df["Close"].iloc[-1])
    color_linea   = "#26a69a" if ultimo_precio >= primer_precio else "#ef5350"

    # Construir gráfico
    fig = go.Figure()

    # Área bajo la curva
    # Convertir color hex a rgba con opacidad
    def hex_a_rgba(hex_color: str, opacidad: float = 0.15) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{opacidad})"

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"],
        mode="lines",
        name="Precio",
        line=dict(color=color_linea, width=2),
        fill="tozeroy",
        fillcolor=hex_a_rgba(color_linea),
    ))

    # Anotación de variación en el período
    variacion_periodo     = ultimo_precio - primer_precio
    variacion_periodo_pct = (variacion_periodo / primer_precio * 100) if primer_precio else 0
    simbolo = "▲" if variacion_periodo >= 0 else "▼"

    fig.update_layout(
        title=dict(
            text=f"{ticker}  {simbolo} {abs(variacion_periodo_pct):.2f}% en {ventana}",
            font=dict(size=13, color="#aaaaaa"),
        ),
        xaxis=dict(
            showgrid=False,
            title="",
            showspikes=True,
            spikecolor="#555555",
            spikethickness=1,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#333333",
            title="",
            tickprefix="$",
            # ← Esta línea es la clave: el eje empieza cerca del precio
            range=[df["Close"].min() * 0.995, df["Close"].max() * 1.005],
        ),
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=350,
        # Fondo transparente para que respete el tema de Streamlit
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_traces(
        hovertemplate="$%{y:,.2f}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)


# ── Datos clave ───────────────────────────────────────────────────────────────

def _render_datos_clave(datos: dict) -> None:
    """Muestra tabla de métricas clave del activo."""

    st.markdown("**Datos clave**")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Volumen", formatear_numero(datos.get("volumen")))
        st.metric("Market Cap", formatear_numero(datos.get("market_cap"), prefijo="$"))

    with col2:
        pe = datos.get("pe_ratio")
        st.metric("P/E Ratio", f"{pe:.2f}" if pe else "N/D")
        div = datos.get("dividendo_yield")
        st.metric("Dividendo Yield", f"{div*100:.2f}%" if div else "N/D")

    with col3:
        max52 = datos.get("semana_52_max")
        st.metric("Máx. 52 semanas", f"${max52:,.2f}" if max52 else "N/D")

    with col4:
        min52 = datos.get("semana_52_min")
        st.metric("Mín. 52 semanas", f"${min52:,.2f}" if min52 else "N/D")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _badge_tipo(tipo: str) -> str:
    """Devuelve un emoji según el tipo de activo."""
    badges = {
        "etf":    "🟦 ETF",
        "equity": "🟩 Acción",
        "crypto": "🟨 Crypto",
        "mutualfund": "🟪 Fondo",
    }
    return badges.get(tipo, "⬜ Otro")
