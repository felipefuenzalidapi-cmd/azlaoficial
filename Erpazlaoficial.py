import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, date

st.set_page_config(page_title="ERP Zapatillas", page_icon="👟", layout="wide")
st.title("👟 ERP para marca de zapatillas")

# ---------------- Configuración de tallas ----------------
SIZES = [35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45]

# ---------------- Estado inicial ----------------
def init_state():
    if "df_inventario" not in st.session_state:
        base_cols = ["Producto","Código","Categoría","Proveedor","Precio","CostoDirecto"]
        size_cols = [f"Talla_{s}" for s in SIZES]
        st.session_state.df_inventario = pd.DataFrame(columns=base_cols + size_cols + ["StockTotal"])
    if "df_ventas" not in st.session_state:
        st.session_state.df_ventas = pd.DataFrame(columns=[
            "Fecha","Producto","Talla","Cantidad","Comprador","PrecioVenta","Comision"
        ])
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
        st.session_state.iva_pct = 19.0
    if "saldo_inicial" not in st.session_state:
        st.session_state.saldo_inicial = 0.0

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

def compute_stock_total(row):
    return int(sum(row.get(f"Talla_{s}", 0) or 0 for s in SIZES))

# ---------------- Funciones de negocio ----------------
def add_product(nombre, codigo, categoria, proveedor, precio, costo, stocks_por_talla):
    df = st.session_state.df_inventario.copy()
    record = {
        "Producto": nombre.strip(),
        "Código": (codigo or "").strip(),
        "Categoría": (categoria or "").strip(),
        "Proveedor": (proveedor or "").strip(),
        "Precio": float(precio),
        "CostoDirecto": float(costo),
    }
    for s in SIZES:
        record[f"Talla_{s}"] = int(stocks_por_talla.get(s, 0))
    record["StockTotal"] = sum(stocks_por_talla.values())
    st.session_state.df_inventario = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

def register_sale(fecha, producto, talla, cantidad, comprador, precio_venta):
    inv = st.session_state.df_inventario.copy()
    idx = inv.index[inv["Producto"] == producto]
    if len(idx) == 0:
        st.error(f"Producto no encontrado: {producto}")
        return False
    i = idx[0]
    talla_col = f"Talla_{talla}"
    if talla_col not in inv.columns:
        st.error(f"Talla no válida: {talla}")
        return False
    stock_talla = int(inv.at[i, talla_col] or 0)
    if cantidad <= 0:
        st.error("La cantidad debe ser mayor a 0.")
        return False
    if stock_talla < cantidad:
        st.warning(f"Stock insuficiente para talla {talla}. Disponible {stock_talla}, solicitado {cantidad}.")
        return False

    # Descontar stock de esa talla y actualizar total
    inv.at[i, talla_col] = stock_talla - cantidad
    inv.at[i, "StockTotal"] = compute_stock_total(inv.loc[i])
    st.session_state.df_inventario = inv

    # Comisión de pasarela
    comision_pct = st.session_state.comision_pasarela / 100.0
    comision = float(precio_venta) * comision_pct

    sales = st.session_state.df_ventas.copy()
    new_sale = pd.DataFrame([{
        "Fecha": to_date_str(fecha),
        "Producto": producto,
        "Talla": str(talla),
        "Cantidad": int(cantidad),
        "Comprador": (comprador or "").strip(),
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
    st.session_state.saldo_inicial = st.number_input("Saldo inicial caja", min_value=0.0, value=float(st.session_state.saldo_inicial), step=10000.0, key="cfg_saldo_inicial")

    st.divider()
    st.subheader("Exportar todo")
    def compute_cash_flow_df():
        IVA = st.session_state.iva_pct / 100.0
        sales = st.session_state.df_ventas.copy()
        exp = st.session_state.df_gastos.copy()
        if not sales.empty:
            sales["Fecha"] = pd.to_datetime(sales["Fecha"])
            sales["Mes"] = sales["Fecha"].dt.to_period("M").astype(str)
            ingresos_netos = (sales["PrecioVenta"] / (1 + IVA)).groupby(sales["Mes"]).sum().rename("IngresosNetos")
            comisiones = sales.groupby("Mes")["Comision"].sum().rename("Comisiones")
        else:
            ingresos_netos = pd.Series(dtype=float, name="IngresosNetos")
            comisiones = pd.Series(dtype=float, name="Comisiones")
        if not exp.empty:
            exp["Fecha"] = pd.to_datetime(exp["Fecha"])
            exp["Mes"] = exp["Fecha"].dt.to_period("M").astype(str)
            gastos = exp.groupby("Mes")["Monto"].sum().rename("Gastos")
        else:
            gastos = pd.Series(dtype=float, name="Gastos")

        flujo = pd.concat([ingresos_netos, comisiones, gastos], axis=1).fillna(0.0)
        flujo["Entradas"] = flujo["IngresosNetos"]
        flujo["Salidas"] = flujo["Comisiones"] + flujo["Gastos"]
        flujo["SaldoNeto"] = flujo["Entradas"] - flujo["Salidas"]
        flujo["SaldoAcumulado"] = st.session_state.saldo_inicial + flujo["SaldoNeto"].cumsum()
        return flujo.reset_index().rename(columns={"index": "Mes"})

    bytes_all = download_excel({
        "Inventario": st.session_state.df_inventario,
        "Ventas": st.session_state.df_ventas,
        "Gastos": st.session_state.df_gastos,
        "Clientes": st.session_state.df_clientes,
        "Proveedores": st.session_state.df_proveedores,
        "FlujoCaja": compute_cash_flow_df()
    })
    st.download_button("Descargar Excel (completo)", data=bytes_all, file_name="erp_zapatillas.xlsx", key="export_excel_all")

# ---------------- Tabs principales ----------------
tab_inv, tab_sales, tab_exp, tab_crm, tab_sup, tab_reports, tab_cf, tab_results = st.tabs(
    ["🗃️ Inventario", "🧾 Ventas", "💸 Gastos", "👥 Clientes", "🏭 Proveedores", "📊 Reportes", "💵 Flujo de caja", "📈 Estado de resultados"]
)

# ---------------- Inventario ----------------
with tab_inv:
    st.subheader("Agregar producto con tallas")
    c1, c2, c3 = st.columns([2,2,2])
    with c1:
        nombre = st.text_input("Nombre del modelo", key="inv_nombre")
        categoria = st.text_input("Categoría", key="inv_categoria")
    with c2:
        codigo = st.text_input("Código", key="inv_codigo")
        proveedor = st.text_input("Proveedor", key="inv_proveedor")
    with c3:
        precio = st.number_input("Precio unitario (venta)", min_value=0.0, value=0.0, step=1000.0, key="inv_precio")
        costo = st.number_input("Costo directo (unitario)", min_value=0.0, value=0.0, step=1000.0, key="inv_costo")

    st.markdown("#### Stock por talla")
    stocks_por_talla = {}
    cols = st.columns(6)
    for idx, s in enumerate(SIZES):
        with cols[idx % 6]:
            stocks_por_talla[s] = st.number_input(f"Talla {s}", min_value=0, value=0, step=1, key=f"inv_talla_{s}")

    if st.button("Agregar producto", type="primary", key="inv_add"):
        if nombre:
            add_product(nombre, codigo, categoria, proveedor, precio, costo, stocks_por_talla)
            st.success("Producto con tallas agregado.")
        else:
            st.error("Ingresa el nombre del modelo.")

    st.divider()
    st.subheader("Inventario actual")
    search_inv = st.text_input("Buscar (modelo, código, categoría, proveedor)", key="inv_search")
    inv_view = st.session_state.df_inventario.copy()
    if not inv_view.empty and search_inv:
        mask = np.column_stack([
            inv_view[col].astype(str).str.contains(search_inv, case=False, na=False)
            for col in ["Producto","Código","Categoría","Proveedor"]
        ]).any(axis=1)
        inv_view = inv_view[mask]
    st.dataframe(inv_view, use_container_width=True)

    # Alertas de stock bajo (por total)
    low_df = st.session_state.df_inventario[st.session_state.df_inventario["StockTotal"] <= st.session_state.low_stock_threshold]
    if low_df.empty:
        st.markdown("✅ No hay modelos con stock total bajo.")
    else:
        st.warning(f"⚠️ Stock total bajo (≤ {st.session_state.low_stock_threshold})")
        st.dataframe(low_df, use_container_width=True)

# ---------------- Ventas ----------------
with tab_sales:
    st.subheader("Registrar venta por talla")
    if st.session_state.df_inventario.empty:
        st.info("Agrega productos primero.")
    else:
        fecha_v = st.date_input("Fecha", datetime.today(), key="ventas_fecha")
        comprador = st.text_input("Nombre del comprador", key="ventas_comprador")

        producto = st.selectbox("Modelo", st.session_state.df_inventario["Producto"].tolist(), key="ventas_producto_sel")
        talla = st.selectbox("Talla", SIZES, key="ventas_talla_sel")
        cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1, key="ventas_cantidad_sel")
        precio_venta = st.number_input("Precio venta (por par)", min_value=0.0, value=0.0, step=1000.0, key="ventas_precio_sel")

        if st.button("Registrar venta", key="ventas_registrar_simple"):
            ok = register_sale(fecha_v, producto, talla, cantidad, comprador, precio_venta)
            if ok:
                st.success("Venta registrada.")

    st.divider()
    st.subheader("Historial de ventas")
    colf1, colf2, colf3 = st.columns([2,1,1])
    with colf1:
        search_v = st.text_input("Buscar (modelo, comprador, talla)", key="ventas_search")
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
        monto = st.number_input("Monto", min_value=0.0, value=0.0, step=1000.0, key="gastos_monto")
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

        st.markdown("#### Ventas por modelo (brutas)")
        by_prod = sales_f.groupby("Producto")["PrecioVenta"].sum().sort_values(ascending=False)
        if not by_prod.empty:
            st.bar_chart(by_prod, use_container_width=True)
        else:
            st.info("Sin ventas en el periodo seleccionado.")

        st.markdown("#### Ventas por talla (pares)")
        by_size = sales_f.groupby("Talla")["Cantidad"].sum().sort_values(ascending=False)
        if not by_size.empty:
            st.bar_chart(by_size, use_container_width=True)
        else:
            st.info("Sin cantidades por talla en el periodo.")

        st.markdown("#### Ventas por mes (brutas)")
        sales_f["Mes"] = sales_f["Fecha"].dt.to_period("M").astype(str)
        by_month = sales_f.groupby("Mes")["PrecioVenta"].sum().sort_values()
        if not by_month.empty:
            st.line_chart(by_month, use_container_width=True)
        else:
            st.info("Sin ventas para graficar por mes.")

        st.markdown("#### Modelo más vendido y cliente top")
        top_prod = most_common(sales_f["Producto"]) if not sales_f.empty else None
        top_client = most_common(sales_f["Comprador"]) if not sales_f.empty else None
        c1, c2 = st.columns(2)
        c1.metric("Modelo top", top_prod if top_prod else "N/A")
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

# ---------------- Flujo de caja ----------------
with tab_cf:
    st.subheader("Flujo de caja")
    c1, c2 = st.columns([1,1])
    with c1:
        cf_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="cf_desde")
    with c2:
        cf_fin = st.date_input("Hasta", value=datetime.today(), key="cf_hasta")

    IVA = st.session_state.iva_pct / 100.0
    sales = st.session_state.df_ventas.copy()
    exp = st.session_state.df_gastos.copy()

    if not sales.empty:
        sales["Fecha"] = pd.to_datetime(sales["Fecha"])
        sf = sales[(sales["Fecha"] >= pd.to_datetime(cf_ini)) & (sales["Fecha"] <= pd.to_datetime(cf_fin))].copy()
        sf["Mes"] = sf["Fecha"].dt.to_period("M").astype(str)
        ingresos_netos_m = (sf["PrecioVenta"] / (1 + IVA)).groupby(sf["Mes"]).sum().rename("IngresosNetos")
        comisiones_m = sf.groupby("Mes")["Comision"].sum().rename("Comisiones")
    else:
        ingresos_netos_m = pd.Series(dtype=float, name="IngresosNetos")
        comisiones_m = pd.Series(dtype=float, name="Comisiones")

    if not exp.empty:
        exp["Fecha"] = pd.to_datetime(exp["Fecha"])
        ef = exp[(exp["Fecha"] >= pd.to_datetime(cf_ini)) & (exp["Fecha"] <= pd.to_datetime(cf_fin))].copy()
        ef["Mes"] = ef["Fecha"].dt.to_period("M").astype(str)
        gastos_m = ef.groupby("Mes")["Monto"].sum().rename("Gastos")
    else:
        gastos_m = pd.Series(dtype=float, name="Gastos")

    flujo_m = pd.concat([ingresos_netos_m, comisiones_m, gastos_m], axis=1).fillna(0.0)
    flujo_m["Entradas"] = flujo_m["IngresosNetos"]
    flujo_m["Salidas"] = flujo_m["Comisiones"] + flujo_m["Gastos"]
    flujo_m["SaldoNeto"] = flujo_m["Entradas"] - flujo_m["Salidas"]
    flujo_m["SaldoAcumulado"] = st.session_state.saldo_inicial + flujo_m["SaldoNeto"].cumsum()

    st.dataframe(flujo_m.reset_index().rename(columns={"index": "Mes"}), use_container_width=True)
    if not flujo_m.empty:
        st.line_chart(flujo_m[["SaldoAcumulado"]])

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
        sales_f = sales[(sales["Fecha"] >= pd.to_datetime(er_ini)) & (sales["Fecha"] <= pd.to_datetime(er_fin))].copy()
    else:
        sales_f = sales

    if not exp.empty:
        exp["Fecha"] = pd.to_datetime(exp["Fecha"])
        exp_f = exp[(exp["Fecha"] >= pd.to_datetime(er_ini)) & (exp["Fecha"] <= pd.to_datetime(er_fin))].copy()
    else:
        exp_f = exp

    # Ingresos netos (sin IVA)
    ingresos_netos = float((sales_f["PrecioVenta"] / (1 + IVA)).sum())

    # Costos directos: costo unitario por producto * cantidad
    if not sales_f.empty and not inv.empty and "CostoDirecto" in inv.columns:
        inv_cost = inv.set_index("Producto")["CostoDirecto"].to_dict()
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
bytes_all_final = download_excel({
    "Inventario": st.session_state.df_inventario,
    "Ventas": st.session_state.df_ventas,
    "Gastos": st.session_state.df_gastos,
    "Clientes": st.session_state.df_clientes,
    "Proveedores": st.session_state.df_proveedores
})
st.download_button("Descargar Excel (todos)", data=bytes_all_final, file_name="erp_zapatillas_todo.xlsx", key="export_excel_all_bottom")
