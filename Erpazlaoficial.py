import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, date

st.set_page_config(page_title="ERP Ligero", page_icon="📦", layout="wide")
st.title("📦 ERP Ligero para tu emprendimiento")

# ---------------- Estado inicial ----------------
def init_state():
    if "df_inventario" not in st.session_state:
        st.session_state.df_inventario = pd.DataFrame(
            columns=["Producto","Código","Categoría","Stock","Precio","CostoDirecto","Proveedor"]
        )
    if "df_ventas" not in st.session_state:
        st.session_state.df_ventas = pd.DataFrame(
            columns=["Fecha","Producto","Cantidad","Comprador","Talla","PrecioVenta","Comision"]
        )
    if "df_gastos" not in st.session_state:
        st.session_state.df_gastos = pd.DataFrame(columns=["Fecha","Tipo","Monto","Nota"])
    if "df_clientes" not in st.session_state:
        st.session_state.df_clientes = pd.DataFrame(columns=["Nombre","Contacto","Notas"])
    if "df_proveedores" not in st.session_state:
        st.session_state.df_proveedores = pd.DataFrame(columns=["Nombre","Contacto","Notas"])
    if "low_stock_threshold" not in st.session_state:
        st.session_state.low_stock_threshold = 5
    if "monthly_budget" not in st.session_state:
        st.session_state.monthly_budget = 0.0
    if "comision_pasarela" not in st.session_state:
        st.session_state.comision_pasarela = 3.5
    if "iva_pct" not in st.session_state:
        st.session_state.iva_pct = 19.0  # IVA Chile por defecto

init_state()

# ---------------- Utilidades ----------------
DATE_FMT = "%Y-%m-%d"

def to_date_str(d):
    if isinstance(d, (date, datetime)):
        return d.strftime(DATE_FMT)
    return pd.to_datetime(d).strftime(DATE_FMT)

def download_excel(df_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in df_dict.items():
            df.to_excel(writer, sheet_name=name[:30], index=False)
    return output.getvalue()

def most_common(series):
    return series.value_counts().idxmax() if not series.empty else None

# ---------------- Funciones de negocio ----------------
def add_product(nombre, codigo, categoria, stock, precio, costo, proveedor):
    df = st.session_state.df_inventario.copy()
    new = pd.DataFrame([{
        "Producto": nombre.strip(),
        "Código": (codigo or "").strip(),
        "Categoría": (categoria or "").strip(),
        "Stock": int(stock),
        "Precio": float(precio),
        "CostoDirecto": float(costo),
        "Proveedor": (proveedor or "").strip()
    }])
    st.session_state.df_inventario = pd.concat([df, new], ignore_index=True)

def register_sale(fecha, producto, cantidad, comprador, talla, precio_venta):
    inv = st.session_state.df_inventario.copy()
    idx = inv.index[inv["Producto"] == producto]
    if len(idx) == 0:
        st.error(f"Producto no encontrado: {producto}")
        return False
    i = idx[0]
    stock_actual = int(inv.at[i, "Stock"])
    if cantidad <= 0:
        st.error("La cantidad debe ser mayor a 0.")
        return False
    if stock_actual < cantidad:
        st.warning(f"Stock insuficiente para {producto}. Disponible {stock_actual}, solicitado {cantidad}.")
        return False
    inv.at[i, "Stock"] = stock_actual - cantidad
    st.session_state.df_inventario = inv

    # Solo comisión de pasarela
    comision_pct = st.session_state.comision_pasarela / 100.0
    comision = float(precio_venta) * comision_pct

    sales = st.session_state.df_ventas.copy()
    new_sale = pd.DataFrame([{
        "Fecha": to_date_str(fecha),
        "Producto": producto,
        "Cantidad": int(cantidad),
        "Comprador": (comprador or "").strip(),
        "Talla": str(talla).strip(),
        "PrecioVenta": float(precio_venta),
        "Comision": comision
    }])
    st.session_state.df_ventas = pd.concat([sales, new_sale], ignore_index=True)
    return True

def add_expense(fecha, tipo, monto, nota):
    exp = st.session_state.df_gastos.copy()
    new = pd.DataFrame([{
        "Fecha": to_date_str(fecha),
        "Tipo": tipo,
        "Monto": float(monto),
        "Nota": (nota or "").strip()
    }])
    st.session_state.df_gastos = pd.concat([exp, new], ignore_index=True)

def add_client(nombre, contacto, notas=""):
    cli = st.session_state.df_clientes.copy()
    new = pd.DataFrame([{"Nombre": nombre.strip(), "Contacto": (contacto or "").strip(), "Notas": (notas or "").strip()}])
    st.session_state.df_clientes = pd.concat([cli, new], ignore_index=True)

def add_supplier(nombre, contacto, notas=""):
    sup = st.session_state.df_proveedores.copy()
    new = pd.DataFrame([{"Nombre": nombre.strip(), "Contacto": (contacto or "").strip(), "Notas": (notas or "").strip()}])
    st.session_state.df_proveedores = pd.concat([sup, new], ignore_index=True)

# ---------------- Barra lateral ----------------
with st.sidebar:
    st.header("Configuración")
    st.session_state.low_stock_threshold = st.number_input("Umbral de stock bajo", min_value=0, value=st.session_state.low_stock_threshold, step=1, key="cfg_stock_umbral")
    st.session_state.monthly_budget = st.number_input("Presupuesto mensual de gastos", min_value=0.0, value=float(st.session_state.monthly_budget), step=500.0, key="cfg_presupuesto")
    st.session_state.comision_pasarela = st.number_input("Comisión Pasarela (%)", min_value=0.0, value=st.session_state.comision_pasarela, step=0.1, key="cfg_pasarela")
    st.session_state.iva_pct = st.number_input("IVA (%)", min_value=0.0, value=st.session_state.iva_pct, step=0.5, key="cfg_iva")

    st.divider()
    st.subheader("Exportar todo")
    bytes_all = download_excel({
        "Inventario": st.session_state.df_inventario,
        "Ventas": st.session_state.df_ventas,
        "Gastos": st.session_state.df_gastos,
        "Clientes": st.session_state.df_clientes,
        "Proveedores": st.session_state.df_proveedores
    })
    st.download_button("Descargar Excel (todos)", data=bytes_all, file_name="erp_ligero.xlsx", key="export_excel_all")

# ---------------- Tabs principales ----------------
tab_inv, tab_sales, tab_exp, tab_crm, tab_sup, tab_reports, tab_results = st.tabs(
    ["🗃️ Inventario", "🧾 Ventas", "💸 Gastos", "👥 Clientes", "🏭 Proveedores", "📊 Reportes", "📈 Estado de resultados"]
)

# ---------------- Inventario ----------------
with tab_inv:
    st.subheader("Agregar producto")
    c1, c2, c3, c4 = st.columns([2,2,2,2])
    with c1:
        nombre = st.text_input("Nombre", key="inv_nombre")
        categoria = st.text_input("Categoría", key="inv_categoria")
    with c2:
        codigo = st.text_input("Código", key="inv_codigo")
        proveedor = st.text_input("Proveedor", key="inv_proveedor")
    with c3:
        stock = st.number_input("Stock inicial", min_value=0, value=0, step=1, key="inv_stock")
        precio = st.number_input("Precio unitario (venta)", min_value=0.0, value=0.0, step=100.0, key="inv_precio")
    with c4:
        costo = st.number_input("Costo directo (unitario)", min_value=0.0, value=0.0, step=100.0, key="inv_costo")
    if st.button("Agregar producto", type="primary", key="inv_add"):
        if nombre:
            add_product(nombre, codigo, categoria, stock, precio, costo, proveedor)
            st.success("Producto agregado.")
        else:
            st.error("Ingresa el nombre del producto.")

    st.divider()
    st.subheader("Inventario actual")
    search_inv = st.text_input("Buscar (nombre, código, categoría, proveedor)", key="inv_search")
    inv_view = st.session_state.df_inventario.copy()
    if search_inv:
        mask = np.column_stack([
            inv_view[col].astype(str).str.contains(search_inv, case=False, na=False)
            for col in ["Producto","Código","Categoría","Proveedor"]
        ]).any(axis=1)
    else:
        mask = np.ones(len(inv_view), dtype=bool)
    inv_view = inv_view[mask]
    st.dataframe(inv_view, use_container_width=True)

    # Alertas de stock bajo
    low_df = st.session_state.df_inventario[st.session_state.df_inventario["Stock"] <= st.session_state.low_stock_threshold]
    if low_df.empty:
        st.markdown("✅ No hay productos con stock bajo.")
    else:
        st.warning(f"⚠️ Stock bajo (≤ {st.session_state.low_stock_threshold})")
        st.dataframe(low_df, use_container_width=True)

# ---------------- Ventas ----------------
with tab_sales:
    st.subheader("Registrar venta múltiple")
    if st.session_state.df_inventario.empty:
        st.info("Agrega productos primero.")
    else:
        fecha_v = st.date_input("Fecha", datetime.today(), key="ventas_fecha")
        comprador = st.text_input("Nombre del comprador", key="ventas_comprador")
        num_items = st.number_input("Número de productos en esta venta", min_value=1, value=1, step=1, key="ventas_num_items")

        items = []
        for i in range(num_items):
            st.markdown(f"**Producto {i+1}**")
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            with c1:
                producto = st.selectbox(f"Producto {i+1}", st.session_state.df_inventario["Producto"].tolist(), key=f"ventas_producto_{i}")
            with c2:
                cantidad = st.number_input(f"Cantidad {i+1}", min_value=1, value=1, step=1, key=f"ventas_cantidad_{i}")
            with c3:
                talla = st.text_input(f"Talla {i+1}", key=f"ventas_talla_{i}")
            with c4:
                precio_venta = st.number_input(f"Precio venta {i+1}", min_value=0.0, value=0.0, step=100.0, key=f"ventas_precio_{i}")
            items.append({"Producto": producto, "Cantidad": cantidad, "Talla": talla, "PrecioVenta": precio_venta})

        if st.button("Registrar venta múltiple", type="secondary", key="ventas_registrar"):
            any_ok = False
            for item in items:
                ok = register_sale(fecha_v, item["Producto"], item["Cantidad"], comprador, item["Talla"], item["PrecioVenta"])
                any_ok = any_ok or ok
            if any_ok:
                st.success("Venta registrada.")
            else:
                st.error("No se pudo registrar la venta. Revisa stock y datos.")

    st.divider()
    st.subheader("Historial de ventas")
    colf1, colf2, colf3 = st.columns([2,1,1])
    with colf1:
        search_v = st.text_input("Buscar (producto, comprador, talla)", key="ventas_search")
    with colf2:
        v_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="ventas_desde")
    with colf3:
        v_fin = st.date_input("Hasta", value=datetime.today(), key="ventas_hasta")
    v_view = st.session_state.df_ventas.copy()
    if not v_view.empty:
        v_view["Fecha"] = pd.to_datetime(v_view["Fecha"])
        v_view = v_view[(v_view["Fecha"] >= pd.to_datetime(v_ini)) & (v_view["Fecha"] <= pd.to_datetime(v_fin))]
        if search_v:
            mask_v = v_view.apply(lambda r: search_v.lower() in str(r.values).lower(), axis=1)
            v_view = v_view[mask_v]
    st.dataframe(v_view, use_container_width=True)

# ---------------- Gastos ----------------
with tab_exp:
    st.subheader("Registrar gasto")
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1:
        fecha_g = st.date_input("Fecha del gasto", datetime.today(), key="gastos_fecha")
    with c2:
        tipo = st.selectbox("Tipo", ["Marketing","Envíos","Costos directos de producto","Shopify mensual","Otros"], key="gastos_tipo")
    with c3:
        monto = st.number_input("Monto", min_value=0.0, value=0.0, step=100.0, key="gastos_monto")
    with c4:
        nota = st.text_input("Nota (opcional)", key="gastos_nota")
    if st.button("Agregar gasto", key="gastos_add"):
        add_expense(fecha_g, tipo, monto, nota)
        st.success("Gasto registrado.")

    st.divider()
    st.subheader("Historial de gastos")
    colg1, colg2, colg3 = st.columns([2,1,1])
    with colg1:
        search_g = st.text_input("Buscar (tipo, nota)", key="gastos_search")
    with colg2:
        g_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="gastos_desde")
    with colg3:
        g_fin = st.date_input("Hasta", value=datetime.today(), key="gastos_hasta")
    g_view = st.session_state.df_gastos.copy()
    if not g_view.empty:
        g_view["Fecha"] = pd.to_datetime(g_view["Fecha"])
        g_view = g_view[(g_view["Fecha"] >= pd.to_datetime(g_ini)) & (g_view["Fecha"] <= pd.to_datetime(g_fin))]
        if search_g:
            mask_g = g_view.apply(lambda r: search_g.lower() in str(r.values).lower(), axis=1)
            g_view = g_view[mask_g]
    st.dataframe(g_view, use_container_width=True)

    # Alerta de presupuesto mensual
    if st.session_state.monthly_budget > 0:
        month_str = datetime.today().strftime("%Y-%m")
        monthly_sum = st.session_state.df_gastos[
            st.session_state.df_gastos["Fecha"].astype(str).str.startswith(month_str)
        ]["Monto"].sum() if not st.session_state.df_gastos.empty else 0.0
        if monthly_sum > st.session_state.monthly_budget:
            st.error(f"Presupuesto mensual superado: {monthly_sum:,.0f} > {st.session_state.monthly_budget:,.0f}")
        else:
            st.info(f"Gastos del mes {month_str}: ${monthly_sum:,.0f} de ${st.session_state.monthly_budget:,.0f}")

# ---------------- Clientes (CRM) ----------------
with tab_crm:
    st.subheader("Registrar cliente")
    c1, c2 = st.columns([2,2])
    with c1:
        cli_nombre = st.text_input("Nombre del cliente", key="crm_cli_nombre")
        cli_contacto = st.text_input("Contacto (teléfono/email)", key="crm_cli_contacto")
    with c2:
        cli_notas = st.text_area("Notas", key="crm_cli_notas")
    if st.button("Agregar cliente", key="crm_cli_add"):
        if cli_nombre:
            add_client(cli_nombre, cli_contacto, cli_notas)
            st.success("Cliente agregado.")
        else:
            st.error("Ingresa el nombre del cliente.")

    st.divider()
    st.subheader("Clientes")
    st.dataframe(st.session_state.df_clientes, use_container_width=True)

    st.subheader("Ranking de clientes")
    if not st.session_state.df_ventas.empty:
        ventas_cli = st.session_state.df_ventas.groupby("Comprador").agg(
            CantidadCompras=("Producto","count"),
            MontoTotal=("PrecioVenta","sum")
        ).reset_index()

        orden = st.radio("Ordenar por:", ["Cantidad de compras","Monto total"], key="crm_orden")
        if orden == "Cantidad de compras":
            ventas_cli = ventas_cli.sort_values("CantidadCompras", ascending=False)
        else:
            ventas_cli = ventas_cli.sort_values("MontoTotal", ascending=False)

        st.dataframe(ventas_cli, use_container_width=True)

    st.subheader("Compras por cliente")
    if not st.session_state.df_ventas.empty:
        cliente_sel = st.selectbox(
            "Selecciona cliente", sorted(st.session_state.df_ventas["Comprador"].dropna().unique().tolist()),
            key="crm_cli_select"
        )
        cli_sales = st.session_state.df_ventas[st.session_state.df_ventas["Comprador"] == cliente_sel]
        total_cli = cli_sales["PrecioVenta"].sum()
        st.metric("Total comprado (bruto)", f"${total_cli:,.0f}")
        st.dataframe(cli_sales, use_container_width=True)

# ---------------- Proveedores ----------------
with tab_sup:
    st.subheader("Registrar proveedor")
    s1, s2 = st.columns([2,2])
    with s1:
        sup_nombre = st.text_input("Nombre del proveedor", key="sup_nombre")
        sup_contacto = st.text_input("Contacto (teléfono/email)", key="sup_contacto")
    with s2:
        sup_notas = st.text_area("Notas proveedor", key="sup_notas")
    if st.button("Agregar proveedor", key="sup_add"):
        if sup_nombre:
            add_supplier(sup_nombre, sup_contacto, sup_notas)
            st.success("Proveedor agregado.")
        else:
            st.error("Ingresa el nombre del proveedor.")

    st.divider()
    st.subheader("Proveedores")
    st.dataframe(st.session_state.df_proveedores, use_container_width=True)

# ---------------- Reportes ----------------
with tab_reports:
    st.subheader("Reportes")
    r1, r2 = st.columns([1,1])
    with r1:
        r_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="rep_desde")
    with r2:
        r_fin = st.date_input("Hasta", value=datetime.today(), key="rep_hasta")

    sales = st.session_state.df_ventas.copy()
    if not sales.empty:
        sales["Fecha"] = pd.to_datetime(sales["Fecha"])
        sales_f = sales[(sales["Fecha"] >= pd.to_datetime(r_ini)) & (sales["Fecha"] <= pd.to_datetime(r_fin))]

        st.markdown("#### Ventas por producto (brutas)")
        by_prod = sales_f.groupby("Producto")["PrecioVenta"].sum().sort_values(ascending=False)
        if not by_prod.empty:
            st.bar_chart(by_prod, use_container_width=True)
        else:
            st.info("Sin ventas en el periodo seleccionado.")

        st.markdown("#### Ventas por mes (brutas)")
        sales_f["Mes"] = sales_f["Fecha"].dt.to_period("M").astype(str)
        by_month = sales_f.groupby("Mes")["PrecioVenta"].sum().sort_values()
        if not by_month.empty:
            st.line_chart(by_month, use_container_width=True)
        else:
            st.info("Sin ventas para graficar por mes.")

        st.markdown("#### Producto más vendido y cliente top")
        top_prod = most_common(sales_f["Producto"]) if not sales_f.empty else None
        top_client = most_common(sales_f["Comprador"]) if not sales_f.empty else None
        c1, c2 = st.columns(2)
        c1.metric("Producto top", top_prod if top_prod else "N/A")
        c2.metric("Cliente top", top_client if top_client else "N/A")
    else:
        st.info("Aún no hay ventas registradas.")

    st.divider()
    st.markdown("#### Gastos por categoría")
    exp = st.session_state.df_gastos.copy()
    if not exp.empty:
        exp["Fecha"] = pd.to_datetime(exp["Fecha"])
        exp_f = exp[(exp["Fecha"] >= pd.to_datetime(r_ini)) & (exp["Fecha"] <= pd.to_datetime(r_fin))]
        by_cat = exp_f.groupby("Tipo")["Monto"].sum().sort_values(ascending=False)
        if not by_cat.empty:
            st.bar_chart(by_cat, use_container_width=True)
        else:
            st.info("Sin gastos en el periodo.")
    else:
        st.info("Aún no hay gastos registrados.")

# ---------------- Estado de resultados ----------------
with tab_results:
    st.subheader("Estado de resultados (neto sin IVA)")
    e1, e2 = st.columns([1,1])
    with e1:
        er_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="er_desde")
    with e2:
        er_fin = st.date_input("Hasta", value=datetime.today(), key="er_hasta")

    IVA = st.session_state.iva_pct / 100.0

    sales = st.session_state.df_ventas.copy()
    exp = st.session_state.df_gastos.copy()
    inv = st.session_state.df_inventario.copy()

    # Filtrar por fechas
    if not sales.empty:
        sales["Fecha"] = pd.to_datetime(sales["Fecha"])
        sales_f = sales[(sales["Fecha"] >= pd.to_datetime(er_ini)) & (sales["Fecha"] <= pd.to_datetime(er_fin))]
    else:
        sales_f = sales

    if not exp.empty:
        exp["Fecha"] = pd.to_datetime(exp["Fecha"])
        exp_f = exp[(exp["Fecha"] >= pd.to_datetime(er_ini)) & (exp["Fecha"] <= pd.to_datetime(er_fin))]
    else:
        exp_f = exp

    # Ingresos netos (sin IVA)
    ingresos_netos = float((sales_f["PrecioVenta"] / (1 + IVA)).sum())

    # Costos directos: costo unitario por producto * cantidad
    if not sales_f.empty and not inv.empty and "CostoDirecto" in inv.columns:
        inv_cost = inv.set_index("Producto")["CostoDirecto"].to_dict()
        sales_f = sales_f.copy()
        sales_f["CostoUnit"] = sales_f["Producto"].map(inv_cost).fillna(0.0)
        costos_directos = float((sales_f["CostoUnit"] * sales_f["Cantidad"]).sum())
    else:
        costos_directos = 0.0

    # Comisiones (solo pasarela)
    comisiones = float(sales_f["Comision"].sum()) if "Comision" in sales_f.columns else 0.0

    # Gastos (incluye Shopify mensual si lo registras allí)
    gastos_totales = float(exp_f["Monto"].sum())

    # Ganancia neta y margen
    ganancia_neta = ingresos_netos - costos_directos - comisiones - gastos_totales
    margen_utilidad = (ganancia_neta / ingresos_netos * 100) if ingresos_netos > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Ingresos netos (sin IVA)", f"${ingresos_netos:,.0f}")
    c2.metric("Costos directos", f"${costos_directos:,.0f}")
    c3.metric("Comisiones pasarela", f"${comisiones:,.0f}")
    c4.metric("Gastos", f"${gastos_totales:,.0f}")
    c5.metric("Ganancia neta", f"${ganancia_neta:,.0f}")
    st.metric("Margen de utilidad %", f"{margen_utilidad:.2f}%")

    st.divider()
    st.markdown("#### Detalle de ventas (periodo)")
    st.dataframe(sales_f, use_container_width=True)
    st.markdown("#### Detalle de gastos (periodo)")
    st.dataframe(exp_f, use_container_width=True)

# ---------------- Exportación al final ----------------
st.divider()
st.subheader("Exportar datos")
bytes_all = download_excel({
    "Inventario": st.session_state.df_inventario,
    "Ventas": st.session_state.df_ventas,
    "Gastos": st.session_state.df_gastos,
    "Clientes": st.session_state.df_clientes,
    "Proveedores": st.session_state.df_proveedores
})
st.download_button("Descargar Excel (todos)", data=bytes_all, file_name="erp_ligero.xlsx", key="export_excel_all_bottom")
