"""
modules/inversiones/operaciones.py
Registro de operaciones de compra y venta.
Maneja múltiples monedas con conversión automática a USD.
Soporta GBX (peniques de libra esterlina).
Confirmación en dos pasos antes de guardar.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from database.db import fetch_all, fetch_one, execute_write
from utils.market_data import get_precio_actual, buscar_ticker, normalizar_moneda, get_tipo_cambio_actual
import yfinance as yf


# ── Tipo de cambio histórico ──────────────────────────────────────────────────

def get_tipo_cambio(moneda: str, fecha: str) -> float:
    """
    Devuelve tipo de cambio a USD en fecha dada.
    Para GBp/GBX divide por 100 automáticamente.
    """
    moneda_norm, factor = normalizar_moneda(moneda)
    if moneda_norm == "USD":
        return 1.0
    try:
        par      = f"{moneda_norm}USD=X"
        ticker   = yf.Ticker(par)
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        fecha_fin = (fecha_dt + timedelta(days=7)).strftime("%Y-%m-%d")
        df = ticker.history(start=fecha, end=fecha_fin)
        if not df.empty:
            return float(df["Close"].iloc[0]) * factor
        info  = ticker.fast_info
        precio = getattr(info, "last_price", None)
        if precio:
            return float(precio) * factor
    except Exception:
        pass
    return factor


# ── Entry point ───────────────────────────────────────────────────────────────

def render() -> None:
    st.title("🔄 Operaciones")
    st.divider()

    tab_compra, tab_venta, tab_historial = st.tabs([
        "➕ Registrar compra",
        "➖ Registrar venta",
        "📋 Historial",
    ])

    with tab_compra:
        _render_formulario_compra()
    with tab_venta:
        _render_formulario_venta()
    with tab_historial:
        _render_historial()


# ── Formulario de compra ──────────────────────────────────────────────────────

def _render_formulario_compra() -> None:
    st.subheader("Nueva compra")

    for key, default in [
        ("compra_ticker_confirmado", ""),
        ("compra_ticker_nombre", ""),
        ("compra_ticker_moneda", "USD"),
        ("compra_confirmada", False),
        ("compra_datos_resumen", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state.get("compra_confirmada"):
        st.success("✅ Compra registrada correctamente.")
        if st.button("➕ Registrar otra compra"):
            _reset_compra()
            st.rerun()
        return

    # ── Paso 1: Buscador ──────────────────────────────────────────────────────
    st.markdown("**Paso 1 — Buscá el activo**")
    col_q, col_btn = st.columns([4, 1])
    with col_q:
        query = st.text_input(
            "Buscar",
            placeholder="Ej: Whitecap, AAPL, CGEO London...",
            label_visibility="collapsed",
            key="buscar_compra_query",
        )
    with col_btn:
        buscar = st.button("🔍 Buscar", use_container_width=True, key="btn_buscar_compra")

    if buscar and query:
        resultados = buscar_ticker(query)
        if resultados:
            st.session_state["buscar_resultados"] = resultados
        else:
            st.warning("No se encontraron resultados.")
            st.session_state.pop("buscar_resultados", None)

    if "buscar_resultados" in st.session_state:
        st.markdown("**Seleccioná el activo:**")
        for r in st.session_state["buscar_resultados"]:
            col_info, col_usar = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"**{r['ticker']}** — {r['nombre']}  \n"
                    f"`{r['tipo'].upper()}` · {r['exchange']}"
                )
            with col_usar:
                if st.button("Usar", key=f"usar_{r['ticker']}"):
                    info   = get_precio_actual(r["ticker"])
                    # Guardar moneda ORIGINAL de yfinance (ej: GBp, no GBP)
                    moneda = info["moneda"] if info and info.get("moneda") else "USD"
                    st.session_state["compra_ticker_confirmado"] = r["ticker"]
                    st.session_state["compra_ticker_nombre"]     = r["nombre"]
                    st.session_state["compra_ticker_moneda"]     = moneda
                    st.session_state.pop("buscar_resultados", None)
                    st.rerun()

    ticker_actual = st.session_state.get("compra_ticker_confirmado", "")
    moneda_actual = st.session_state.get("compra_ticker_moneda", "USD")

    if ticker_actual:
        col_sel, col_limpiar = st.columns([4, 1])
        with col_sel:
            st.success(f"✅ **{ticker_actual}** · moneda: **{moneda_actual}**")
        with col_limpiar:
            if st.button("✖ Limpiar", key="btn_limpiar_ticker"):
                st.session_state["compra_ticker_confirmado"] = ""
                st.session_state["compra_ticker_moneda"]     = "USD"
                st.rerun()

    st.divider()

    # ── Paso 2: Campos editables ──────────────────────────────────────────────
    st.markdown("**Paso 2 — Completá los datos**")

    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input(
            "Ticker *",
            value=st.session_state.get("compra_ticker_confirmado", ""),
            placeholder="Ej: AAPL, WCP.TO, CGEO.L",
        ).upper().strip()

        cantidad = st.number_input("Cantidad de acciones *", min_value=1, step=1, format="%d",
                                   key="compra_cantidad")
        comision = st.number_input("Comisión (moneda origen)", min_value=0.0, step=0.01,
                                   format="%.2f", key="compra_comision")

    with col2:
        fecha = st.date_input("Fecha de compra *", value=date.today(), max_value=date.today())

        moneda = st.text_input(
            "Moneda del activo",
            value=st.session_state.get("compra_ticker_moneda", "USD"),
            help="USD, CAD, GBP, GBp, EUR, etc. Se detecta automáticamente.",
        ).strip()

        precio = st.number_input(
            "Precio por acción (moneda origen) *",
            min_value=0.0001, value=0.0001, step=0.01, format="%.4f",
            key="compra_precio",
        )
        notas = st.text_input("Notas (opcional)", key="compra_notas")

    # ── Paso 3: Resumen ───────────────────────────────────────────────────────
    st.divider()
    col_ver, _ = st.columns([1, 3])
    with col_ver:
        ver_resumen = st.button("🔄 Ver / actualizar resumen", use_container_width=True)

    if ver_resumen and ticker and cantidad and precio:
        with st.spinner(f"Obteniendo tipo de cambio {moneda}/USD para {fecha}..."):
            tc = get_tipo_cambio(moneda, fecha.isoformat())
        moneda_norm, factor = normalizar_moneda(moneda)
        precio_usd  = precio * tc
        monto_usd   = cantidad * precio_usd + comision * tc

        st.session_state["compra_datos_resumen"] = {
            "ticker":     ticker,
            "nombre":     st.session_state.get("compra_ticker_nombre", ticker),
            "fecha":      fecha.isoformat(),
            "cantidad":   cantidad,
            "precio":     precio,
            "comision":   comision,
            "moneda":     moneda,          # Original: GBp, CAD, etc.
            "moneda_norm":moneda_norm,     # Normalizada: GBP, CAD, etc.
            "factor":     factor,
            "tc":         tc,
            "precio_usd": precio_usd,
            "monto_usd":  monto_usd,
            "notas":      notas,
        }

    resumen = st.session_state.get("compra_datos_resumen")
    if resumen:
        factor    = resumen["factor"]
        tc        = resumen["tc"]
        moneda_n  = resumen["moneda_norm"]
        es_gbx    = factor < 1.0

        if es_gbx:
            detalle = (
                f"Precio en {resumen['moneda']}: **{resumen['precio']:,.4f} GBX**  \n"
                f"Precio en GBP: **{resumen['precio'] * factor:,.4f} GBP**  \n"
                f"TC GBP/USD al {resumen['fecha']}: **{tc / factor:.4f}**  \n"
                f"Precio en USD: **${resumen['precio_usd']:,.4f}**"
            )
        elif moneda_n != "USD":
            detalle = (
                f"Precio en {moneda_n}: **{resumen['precio']:,.4f} {moneda_n}**  \n"
                f"TC {moneda_n}/USD al {resumen['fecha']}: **{tc:.4f}**  \n"
                f"Precio en USD: **${resumen['precio_usd']:,.4f}**"
            )
        else:
            detalle = f"Precio: **${resumen['precio']:,.4f} USD**"

        st.warning(
            f"### 📋 Resumen de la compra\n\n"
            f"**Ticker:** {resumen['ticker']} — {resumen['nombre']}  \n"
            f"**Fecha:** {resumen['fecha']}  \n"
            f"**Cantidad:** {int(resumen['cantidad']):,} acciones  \n"
            f"{detalle}  \n"
            f"**Comisión:** {resumen['comision']:,.2f} {resumen['moneda']} "
            f"= ${resumen['comision'] * tc:,.2f} USD  \n"
            f"**Notas:** {resumen['notas'] or '—'}  \n\n"
            f"---\n"
            f"💵 **Monto total: ${resumen['monto_usd']:,.2f} USD**"
        )

        col_conf, col_cancel = st.columns(2)
        with col_conf:
            if st.button("✅ Confirmar compra", type="primary", use_container_width=True):
                _ejecutar_compra(resumen)
        with col_cancel:
            if st.button("✖ Cancelar", type="secondary", use_container_width=True):
                st.session_state["compra_datos_resumen"] = None
                st.rerun()


def _ejecutar_compra(resumen: dict) -> None:
    ticker     = resumen["ticker"]
    nombre     = resumen["nombre"]
    fecha      = resumen["fecha"]
    cantidad   = resumen["cantidad"]
    precio     = resumen["precio"]
    comision   = resumen["comision"]
    moneda     = resumen["moneda"]      # Original: GBp
    tc         = resumen["tc"]
    precio_usd = resumen["precio_usd"]
    notas      = resumen["notas"]
    comision_usd = comision * tc

    try:
        # Guardar moneda ORIGINAL en activos (GBp, no GBP)
        _upsert_activo(ticker, nombre, moneda)

        op_id = execute_write(
            """INSERT INTO operaciones
               (ticker, tipo, fecha, cantidad, precio_unitario, comision,
                moneda, tipo_cambio_usd, notas, fuente)
               VALUES (?, 'compra', ?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (ticker, fecha, cantidad, precio, comision, moneda, tc, notas or None),
        )
        execute_write(
            """INSERT INTO lotes
               (operacion_id, ticker, fecha_compra, cantidad_original,
                cantidad_restante, precio_compra, comision_proporcional)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (op_id, ticker, fecha, cantidad, cantidad, precio_usd, comision_usd),
        )
        _actualizar_posicion(ticker)
        st.session_state["compra_confirmada"]    = True
        st.session_state["compra_datos_resumen"] = None
        _reset_session_ticker()
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al guardar la compra: {e}")


# ── Formulario de venta ───────────────────────────────────────────────────────

def _render_formulario_venta() -> None:
    st.subheader("Registrar venta")

    if "venta_datos_resumen" not in st.session_state:
        st.session_state["venta_datos_resumen"] = None
    if "venta_confirmada" not in st.session_state:
        st.session_state["venta_confirmada"] = False

    if st.session_state.get("venta_confirmada"):
        st.success("✅ Venta registrada correctamente.")
        if st.button("➕ Registrar otra venta"):
            st.session_state["venta_confirmada"]    = False
            st.session_state["venta_datos_resumen"] = None
            st.rerun()
        return

    posiciones = fetch_all(
        """SELECT p.ticker, p.cantidad_total, p.costo_base_total, a.nombre, a.moneda
           FROM posiciones p
           LEFT JOIN activos a ON p.ticker = a.ticker
           WHERE p.cantidad_total > 0"""
    )

    if not posiciones:
        st.info("No tenés posiciones abiertas para vender.")
        return

    tickers_disponibles = [p["ticker"] for p in posiciones]
    posiciones_dict     = {p["ticker"]: p for p in posiciones}

    col1, col2 = st.columns(2)
    with col1:
        ticker = st.selectbox("Ticker *", options=tickers_disponibles)
        if ticker and ticker in posiciones_dict:
            p = posiciones_dict[ticker]
            moneda_activo = p.get("moneda") or "USD"
            st.caption(f"Disponible: {int(p['cantidad_total']):,} acciones · moneda: {moneda_activo}")
        cantidad = st.number_input("Cantidad a vender *", min_value=1, step=1, format="%d",
                                   key="venta_cantidad")
        comision = st.number_input("Comisión (moneda origen)", min_value=0.0, step=0.01,
                                   format="%.2f", key="venta_comision")
    with col2:
        fecha  = st.date_input("Fecha de venta *", value=date.today(), max_value=date.today())
        precio = st.number_input("Precio de venta (moneda origen) *", min_value=0.0001,
                                 step=0.01, format="%.4f", key="venta_precio")
        notas  = st.text_input("Notas (opcional)", key="notas_venta")

    st.divider()
    col_ver, _ = st.columns([1, 3])
    with col_ver:
        ver_resumen = st.button("🔄 Ver / actualizar resumen", use_container_width=True,
                                key="ver_resumen_venta")

    if ver_resumen and ticker and cantidad and precio:
        errores = _validar_operacion(ticker, cantidad, precio, fecha)
        if ticker in posiciones_dict and cantidad > posiciones_dict[ticker]["cantidad_total"]:
            errores.append(f"No podés vender más de {int(posiciones_dict[ticker]['cantidad_total']):,} acciones.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            moneda_activo = posiciones_dict[ticker].get("moneda") or "USD"
            with st.spinner(f"Obteniendo tipo de cambio {moneda_activo}/USD..."):
                tc = get_tipo_cambio(moneda_activo, fecha.isoformat())
            moneda_norm, factor = normalizar_moneda(moneda_activo)
            precio_usd      = precio * tc
            comision_usd    = comision * tc
            posicion        = posiciones_dict[ticker]
            precio_promedio = posicion["costo_base_total"] / posicion["cantidad_total"]
            ganancia_usd    = cantidad * (precio_usd - precio_promedio) - comision_usd
            rentabilidad    = (ganancia_usd / (cantidad * precio_promedio) * 100) if precio_promedio else 0
            monto_venta_usd = cantidad * precio_usd - comision_usd

            st.session_state["venta_datos_resumen"] = {
                "ticker": ticker, "fecha": fecha.isoformat(), "cantidad": cantidad,
                "precio": precio, "comision": comision, "moneda": moneda_activo,
                "moneda_norm": moneda_norm, "factor": factor, "tc": tc,
                "precio_usd": precio_usd, "comision_usd": comision_usd,
                "precio_promedio": precio_promedio, "ganancia_usd": ganancia_usd,
                "rentabilidad": rentabilidad, "monto_venta_usd": monto_venta_usd,
                "notas": notas,
            }

    resumen = st.session_state.get("venta_datos_resumen")
    if resumen:
        ganancia     = resumen["ganancia_usd"]
        rentabilidad = resumen["rentabilidad"]
        color_emoji  = "📈" if ganancia >= 0 else "📉"
        signo        = "+" if ganancia >= 0 else ""
        moneda_n     = resumen["moneda_norm"]
        tc           = resumen["tc"]
        factor       = resumen["factor"]
        es_gbx       = factor < 1.0

        if es_gbx:
            detalle = (
                f"Precio en {resumen['moneda']}: **{resumen['precio']:,.4f} GBX**  \n"
                f"Precio en GBP: **{resumen['precio'] * factor:,.4f} GBP**  \n"
                f"TC GBP/USD: **{tc / factor:.4f}**  \n"
                f"Precio en USD: **${resumen['precio_usd']:,.4f}**"
            )
        elif moneda_n != "USD":
            detalle = (
                f"Precio en {moneda_n}: **{resumen['precio']:,.4f} {moneda_n}**  \n"
                f"TC {moneda_n}/USD: **{tc:.4f}**  \n"
                f"Precio en USD: **${resumen['precio_usd']:,.4f}**"
            )
        else:
            detalle = f"Precio: **${resumen['precio']:,.4f} USD**"

        st.warning(
            f"### 📋 Resumen de la venta {color_emoji}\n\n"
            f"**Ticker:** {resumen['ticker']}  \n"
            f"**Fecha:** {resumen['fecha']}  \n"
            f"**Cantidad:** {int(resumen['cantidad']):,} acciones  \n"
            f"{detalle}  \n"
            f"**Monto venta:** ${resumen['monto_venta_usd']:,.2f} USD  \n\n"
            f"---\n"
            f"**P. promedio compra:** ${resumen['precio_promedio']:,.4f} USD  \n"
            f"**Ganancia / Pérdida:** **{signo}${ganancia:,.2f} USD**  \n"
            f"**Rentabilidad:** **{signo}{rentabilidad:.2f}%**"
        )

        col_conf, col_cancel = st.columns(2)
        with col_conf:
            if st.button("✅ Confirmar venta", type="primary", use_container_width=True):
                _ejecutar_venta(resumen)
        with col_cancel:
            if st.button("✖ Cancelar", type="secondary", use_container_width=True,
                         key="cancel_venta"):
                st.session_state["venta_datos_resumen"] = None
                st.rerun()


def _ejecutar_venta(resumen: dict) -> None:
    try:
        op_id = execute_write(
            """INSERT INTO operaciones
               (ticker, tipo, fecha, cantidad, precio_unitario, comision,
                moneda, tipo_cambio_usd, notas, fuente)
               VALUES (?, 'venta', ?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (resumen["ticker"], resumen["fecha"], resumen["cantidad"],
             resumen["precio"], resumen["comision"], resumen["moneda"],
             resumen["tc"], resumen["notas"] or None),
        )
        _procesar_venta_fifo(
            resumen["ticker"], resumen["fecha"], resumen["cantidad"],
            resumen["precio_usd"], resumen["comision_usd"], op_id,
        )
        _actualizar_posicion(resumen["ticker"])
        st.session_state["venta_confirmada"]    = True
        st.session_state["venta_datos_resumen"] = None
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al guardar la venta: {e}")


# ── Historial ─────────────────────────────────────────────────────────────────

def _render_historial() -> None:
    st.subheader("Historial de operaciones")

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_ticker = st.text_input("Filtrar por ticker", placeholder="Todos").upper().strip()
    with col2:
        filtro_tipo = st.selectbox("Tipo", ["Todos", "Compra", "Venta"])
    with col3:
        filtro_anio = st.selectbox("Año", ["Todos"] + list(range(date.today().year, 2019, -1)))

    query  = "SELECT * FROM operaciones WHERE 1=1"
    params = []
    if filtro_ticker:
        query += " AND ticker = ?"
        params.append(filtro_ticker)
    if filtro_tipo != "Todos":
        query += " AND tipo = ?"
        params.append(filtro_tipo.lower())
    if filtro_anio != "Todos":
        query += " AND strftime('%Y', fecha) = ?"
        params.append(str(filtro_anio))
    query += " ORDER BY fecha DESC, id DESC"

    operaciones = fetch_all(query, tuple(params))
    if not operaciones:
        st.info("No hay operaciones registradas con esos filtros.")
        return

    df = pd.DataFrame(operaciones)
    df["monto_origen"] = df["cantidad"] * df["precio_unitario"] + df["comision"]
    df["monto_usd"]    = df["monto_origen"] * df["tipo_cambio_usd"].fillna(1.0)
    df["tipo"]         = df["tipo"].str.capitalize()
    df["cantidad"]     = df["cantidad"].astype(int)

    df_display = df[[
        "id", "fecha", "tipo", "ticker", "cantidad", "moneda",
        "precio_unitario", "tipo_cambio_usd", "monto_origen", "monto_usd", "notas"
    ]].copy()
    df_display.columns = [
        "ID", "Fecha", "Tipo", "Ticker", "Cantidad", "Moneda",
        "Precio (orig.)", "TC a USD", "Monto (orig.)", "Monto USD", "Notas"
    ]

    def colorear_fila(row):
        color = "background-color: rgba(38, 166, 154, 0.1)" if row["Tipo"] == "Compra" \
                else "background-color: rgba(239, 83, 80, 0.1)"
        return [color] * len(row)

    st.dataframe(
        df_display.style.apply(colorear_fila, axis=1).format({
            "Cantidad":       "{:,}",
            "Precio (orig.)": "{:,.4f}",
            "TC a USD":       "{:.6f}",
            "Monto (orig.)":  "{:,.2f}",
            "Monto USD":      "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    total_compras = df[df["tipo"] == "Compra"]["monto_usd"].sum()
    total_ventas  = df[df["tipo"] == "Venta"]["monto_usd"].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total invertido (USD)", f"${total_compras:,.2f}")
    col2.metric("Total recuperado (USD)", f"${total_ventas:,.2f}")
    col3.metric("Neto (USD)", f"${total_compras - total_ventas:,.2f}")

    st.divider()
    st.markdown("**🗑️ Eliminar operación**")
    st.caption("Usá esto solo para corregir errores de carga.")

    col1, col2 = st.columns([3, 1])
    with col1:
        opciones = {
            str(op["id"]): (
                f"#{op['id']} — {op['tipo'].capitalize()} · {op['ticker']} · "
                f"{int(op['cantidad']):,} acc. @ {op['precio_unitario']:,.4f} "
                f"{op.get('moneda') or 'USD'} · {op['fecha']}"
            )
            for op in operaciones
        }
        op_id_eliminar = st.selectbox(
            "Operación", options=list(opciones.keys()),
            format_func=lambda x: opciones[x], label_visibility="collapsed",
        )
    with col2:
        if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
            _eliminar_operacion(int(op_id_eliminar))


# ── DB helpers ────────────────────────────────────────────────────────────────

def _procesar_venta_fifo(ticker, fecha_venta, cantidad_vender, precio_venta_usd, comision_usd, op_id):
    lotes = fetch_all(
        """SELECT * FROM lotes WHERE ticker = ? AND cantidad_restante > 0 AND cerrado = 0
           ORDER BY fecha_compra ASC""",
        (ticker,),
    )
    cantidad_pendiente  = cantidad_vender
    comision_por_accion = comision_usd / cantidad_vender if cantidad_vender else 0

    for lote in lotes:
        if cantidad_pendiente <= 0:
            break
        usar = min(lote["cantidad_restante"], cantidad_pendiente)
        comision_compra_prop = (
            (lote["comision_proporcional"] / lote["cantidad_original"]) * usar
            if lote["cantidad_original"] else 0
        )
        execute_write(
            """INSERT INTO operaciones_cerradas
               (ticker, lote_id, operacion_venta_id, fecha_compra, fecha_venta,
                cantidad, precio_compra, precio_venta, comision_compra, comision_venta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, lote["id"], op_id, lote["fecha_compra"], fecha_venta,
             usar, lote["precio_compra"], precio_venta_usd,
             comision_compra_prop, comision_por_accion * usar),
        )
        nueva_cantidad = lote["cantidad_restante"] - usar
        execute_write(
            "UPDATE lotes SET cantidad_restante = ?, cerrado = ? WHERE id = ?",
            (nueva_cantidad, 1 if nueva_cantidad == 0 else 0, lote["id"]),
        )
        cantidad_pendiente -= usar


def _actualizar_posicion(ticker):
    resultado = fetch_one(
        """SELECT SUM(cantidad_restante)                 AS cantidad_total,
                  SUM(cantidad_restante * precio_compra) AS costo_base_total,
                  MIN(fecha_compra)                      AS primera_compra
           FROM lotes WHERE ticker = ? AND cerrado = 0""",
        (ticker,),
    )
    if resultado and resultado["cantidad_total"]:
        execute_write(
            """INSERT INTO posiciones (ticker, cantidad_total, costo_base_total, primera_compra)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                   cantidad_total   = excluded.cantidad_total,
                   costo_base_total = excluded.costo_base_total,
                   primera_compra   = excluded.primera_compra,
                   actualizado      = datetime('now')""",
            (ticker, resultado["cantidad_total"],
             resultado["costo_base_total"], resultado["primera_compra"]),
        )
    else:
        execute_write(
            "UPDATE posiciones SET cantidad_total = 0, costo_base_total = 0 WHERE ticker = ?",
            (ticker,),
        )


def _upsert_activo(ticker, nombre=None, moneda="USD"):
    """Inserta el activo guardando la moneda ORIGINAL (ej: GBp, no GBP)."""
    if fetch_one("SELECT ticker FROM activos WHERE ticker = ?", (ticker,)):
        execute_write(
            "UPDATE activos SET moneda = ? WHERE ticker = ?",
            (moneda, ticker),
        )
        return
    execute_write(
        "INSERT OR REPLACE INTO activos (ticker, nombre, tipo, sector, industria, moneda) VALUES (?, ?, 'otro', NULL, NULL, ?)",
        (ticker, nombre or ticker, moneda),
    )


def _eliminar_operacion(op_id):
    try:
        op = fetch_one("SELECT * FROM operaciones WHERE id = ?", (op_id,))
        if not op:
            st.error("No se encontró la operación.")
            return
        ticker = op["ticker"]
        if op["tipo"] == "compra":
            execute_write("DELETE FROM lotes WHERE operacion_id = ?", (op_id,))
        elif op["tipo"] == "venta":
            lotes_afectados = fetch_all(
                "SELECT * FROM operaciones_cerradas WHERE operacion_venta_id = ?", (op_id,)
            )
            for lote in lotes_afectados:
                execute_write(
                    "UPDATE lotes SET cantidad_restante = cantidad_restante + ?, cerrado = 0 WHERE id = ?",
                    (lote["cantidad"], lote["lote_id"]),
                )
            execute_write("DELETE FROM operaciones_cerradas WHERE operacion_venta_id = ?", (op_id,))
        execute_write("DELETE FROM operaciones WHERE id = ?", (op_id,))
        _actualizar_posicion(ticker)
        st.success(f"✅ Operación #{op_id} eliminada y posición recalculada.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al eliminar: {e}")


def _reset_compra():
    st.session_state["compra_confirmada"]    = False
    st.session_state["compra_datos_resumen"] = None
    _reset_session_ticker()


def _reset_session_ticker():
    st.session_state["compra_ticker_confirmado"] = ""
    st.session_state["compra_ticker_nombre"]     = ""
    st.session_state["compra_ticker_moneda"]     = "USD"


def _validar_operacion(ticker, cantidad, precio, fecha):
    errores = []
    if not ticker:
        errores.append("El ticker es obligatorio.")
    if cantidad <= 0:
        errores.append("La cantidad debe ser mayor a 0.")
    if precio <= 0:
        errores.append("El precio debe ser mayor a 0.")
    if fecha > date.today():
        errores.append("La fecha no puede ser futura.")
    return errores