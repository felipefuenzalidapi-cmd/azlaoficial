import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, date

# =========================
# Configuración general
# =========================
st.set_page_config(page_title="ERP Zapatillas", page_icon="👟", layout="wide")

# Encabezado y dashboard inicial
st.title("👟 ERP para marca de zapatillas")
st.markdown("---")

# =========================
# Catálogos de tallas y tipos
# =========================
TALLAS_ZAPATILLAS = [35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
TALLAS_ROPA = ["XS", "S", "M", "L", "XL"]
TIPOS_PRODUCTO = ["Zapatillas", "Ropa", "Otro"]

# =========================
# Estado inicial
# =========================
def init_state():
    # Inventario
    if "df_inventario" not in st.session_state:
        base_cols = ["Tipo", "Producto", "Código", "Categoría", "Proveedor", "Precio", "CostoDirecto"]
        shoe_cols = [f"Talla_{t}" for t in TALLAS_ZAPATILLAS]
        ropa_cols = [f"Talla_{t}" for t in TALLAS_ROPA]
        st.session_state.df_inventario = pd.DataFrame(columns=base_cols + shoe_cols + ropa_cols + ["StockTotal"])
    # Ventas
    if "df_ventas" not in st.session_state:
        st.session_state.df_ventas = pd.DataFrame(columns=[
            "Fecha", "Producto", "Tipo", "Talla", "Cantidad", "Comprador", "PrecioVenta", "Comision"
        ])
    # Gastos
    if "df_gastos" not in st.session_state:
        st.session_state.df_gastos = pd.DataFrame(columns=["Fecha", "Tipo", "Monto", "Nota"])
    # Clientes
    if "df_clientes" not in st.session_state:
        st.session_state.df_clientes = pd.DataFrame(columns=["Nombre", "Contacto", "Notas"])
    # Proveedores
    if "df_proveedores" not in st.session_state:
        st.session_state.df_proveedores = pd.DataFrame(columns=["Nombre", "Contacto", "Notas"])

    # Configuraciones
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

# =========================
# Utilidades
# =========================
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

def ensure_inventory_columns(df):
    base_cols = ["Tipo", "Producto", "Código", "Categoría", "Proveedor", "Precio", "CostoDirecto"]
    shoe_cols = [f"Talla_{t}" for t in TALLAS_ZAPATILLAS]
    ropa_cols = [f"Talla_{t}" for t in TALLAS_ROPA]
    all_cols = base_cols + shoe_cols + ropa_cols + ["StockTotal"]
    for c in all_cols:
        if c not in df.columns:
            df[c] = 0 if c.startswith("Talla_") or c == "StockTotal" else ""
    return df[all_cols]

def compute_stock_total_row(row):
    total = 0
    for col in [f"Talla_{t}" for t in TALLAS_ZAPATILLAS] + [f"Talla_{t}" for t in TALLAS_ROPA]:
        total += int(row.get(col, 0) or 0)
    return int(total)

# =========================
# Inventario: agregar/ajustar
# =========================
def add_product(tipo, nombre, codigo, categoria, proveedor, precio, costo, stocks_por_talla, stock_otro=None):
    df = ensure_inventory_columns(st.session_state.df_inventario.copy())
    record = {
        "Tipo": tipo,
        "Producto": nombre.strip(),
        "Código": (codigo or "").strip(),
        "Categoría": (categoria or "").strip(),
        "Proveedor": (proveedor or "").strip(),
        "Precio": float(precio),
        "CostoDirecto": float(costo),
    }
    # Inicializar tallas en 0
    for t in TALLAS_ZAPATILLAS:
        record[f"Talla_{t}"] = 0
    for t in TALLAS_ROPA:
        record[f"Talla_{t}"] = 0

    if tipo == "Zapatillas":
        for t, qty in stocks_por_talla.items():
            record[f"Talla_{t}"] = int(qty)
        record["StockTotal"] = sum(int(q) for q in stocks_por_talla.values())
    elif tipo == "Ropa":
        for t, qty in stocks_por_talla.items():
            record[f"Talla_{t}"] = int(qty)
        record["StockTotal"] = sum(int(q) for q in stocks_por_talla.values())
    else:
        record["StockTotal"] = int(stock_otro or 0)

    st.session_state.df_inventario = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    st.success("Producto agregado al inventario.")

def decrement_inventory_for_sale(producto, tipo, talla, cantidad):
    inv = ensure_inventory_columns(st.session_state.df_inventario.copy())
    idxs = inv.index[inv["Producto"] == producto]
    if len(idxs) == 0:
        st.error(f"Producto no encontrado: {producto}")
        return False
    i = idxs[0]

    if tipo in ["Zapatillas", "Ropa"]:
        talla_col = f"Talla_{talla}"
        if talla_col not in inv.columns:
            st.error(f"Talla no válida: {talla}")
            return False
        stock = int(inv.at[i, talla_col] or 0)
        if stock < cantidad:
            st.warning(f"Stock insuficiente para talla {talla}. Disponible {stock}, solicitado {cantidad}.")
            return False
        inv.at[i, talla_col] = stock - cantidad
    else:
        stock_total = int(inv.at[i, "StockTotal"] or 0)
        if stock_total < cantidad:
            st.warning(f"Stock total insuficiente. Disponible {stock_total}, solicitado {cantidad}.")
            return False
        inv.at[i, "StockTotal"] = stock_total - cantidad

    inv.at[i, "StockTotal"] = compute_stock_total_row(inv.loc[i])
    st.session_state.df_inventario = inv
    return True

def increment_inventory_for_sale(producto, tipo, talla, cantidad):
    inv = ensure_inventory_columns(st.session_state.df_inventario.copy())
    idxs = inv.index[inv["Producto"] == producto]
    if len(idxs) == 0:
        # Si no existe (ej. fue eliminado), no podemos devolver stock
        return False
    i = idxs[0]

    if tipo in ["Zapatillas", "Ropa"]:
        talla_col = f"Talla_{talla}"
        if talla_col not in inv.columns:
            return False
        stock = int(inv.at[i, talla_col] or 0)
        inv.at[i, talla_col] = stock + cantidad
    else:
        stock_total = int(inv.at[i, "StockTotal"] or 0)
        inv.at[i, "StockTotal"] = stock_total + cantidad

    inv.at[i, "StockTotal"] = compute_stock_total_row(inv.loc[i])
    st.session_state.df_inventario = inv
    return True

# =========================
# Ventas: registrar (simple/múltiple)
# =========================
def register_sale(fecha, producto, tipo, talla, cantidad, comprador, precio_venta):
    ok = decrement_inventory_for_sale(producto, tipo, talla, cantidad)
    if not ok:
        return False

    comision_pct = st.session_state.comision_pasarela / 100.0
    comision = float(precio_venta) * comision_pct

    sales = st.session_state.df_ventas.copy()
    new_sale = pd.DataFrame([{
        "Fecha": to_date_str(fecha),
        "Producto": producto,
        "Tipo": tipo,
        "Talla": str(talla) if talla is not None else "-",
        "Cantidad": int(cantidad),
        "Comprador": (comprador or "").strip(),
        "PrecioVenta": float(precio_venta),
        "Comision": comision
    }])
    st.session_state.df_ventas = pd.concat([sales, new_sale], ignore_index=True)
    return True

def register_multi_sale(fecha, comprador, items):
    # Validaciones previas
    sim_inv = ensure_inventory_columns(st.session_state.df_inventario.copy())
    for item in items:
        producto = item["Producto"]
        tipo = item["Tipo"]
        talla = item.get("Talla", None)
        cantidad = int(item["Cantidad"])
        idxs = sim_inv.index[sim_inv["Producto"] == producto]
        if len(idxs) == 0:
            st.error(f"Producto no encontrado: {producto}")
            return False
        i = idxs[0]
        if tipo in ["Zapatillas", "Ropa"]:
            talla_col = f"Talla_{talla}"
            if talla_col not in sim_inv.columns:
                st.error(f"Talla no válida para {tipo}: {talla}")
                return False
            stock = int(sim_inv.at[i, talla_col] or 0)
            if stock < cantidad:
                st.warning(f"Stock insuficiente: {producto} talla {talla}. Disponible {stock}, solicitado {cantidad}.")
                return False
        else:
            stock_total = int(sim_inv.at[i, "StockTotal"] or 0)
            if stock_total < cantidad:
                st.warning(f"Stock insuficiente: {producto} (Otro). Disponible {stock_total}, solicitado {cantidad}.")
                return False

    # Aplicar
    for item in items:
        producto = item["Producto"]
        tipo = item["Tipo"]
        talla = item.get("Talla", None)
        cantidad = int(item["Cantidad"])
        precio_venta = float(item["PrecioVenta"])
        ok = register_sale(fecha, producto, tipo, talla, cantidad, comprador, precio_venta)
        if not ok:
            return False
    return True

# =========================
# Gastos / Clientes / Proveedores
# =========================
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

# =========================
# Barra lateral
# =========================
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
        "Inventario": ensure_inventory_columns(st.session_state.df_inventario.copy()),
        "Ventas": st.session_state.df_ventas.copy(),
        "Gastos": st.session_state.df_gastos.copy(),
        "Clientes": st.session_state.df_clientes.copy(),
        "Proveedores": st.session_state.df_proveedores.copy(),
        "FlujoCaja": compute_cash_flow_df()
    })
    st.download_button("Descargar Excel (completo)", data=bytes_all, file_name="erp_zapatillas.xlsx", key="export_excel_all")

# =========================
# Dashboard inicial
# =========================
st.header("📊 Dashboard")
month_str = datetime.today().strftime("%Y-%m")
ventas_mes = st.session_state.df_ventas[
    st.session_state.df_ventas["Fecha"].astype(str).str.startswith(month_str)
]["PrecioVenta"].sum() if not st.session_state.df_ventas.empty else 0.0
gastos_mes = st.session_state.df_gastos[
    st.session_state.df_gastos["Fecha"].astype(str).str.startswith(month_str)
]["Monto"].sum() if not st.session_state.df_gastos.empty else 0.0
margen_mes = ventas_mes - gastos_mes

m1, m2, m3 = st.columns(3)
m1.metric("💰 Ventas del mes", f"${ventas_mes:,.0f}")
m2.metric("💸 Gastos del mes", f"${gastos_mes:,.0f}")
m3.metric("📈 Margen neto", f"${margen_mes:,.0f}")

# Gráfico rápido de ventas por producto (mes actual si hay)
if not st.session_state.df_ventas.empty:
    ventas_df = st.session_state.df_ventas.copy()
    ventas_df["Fecha"] = pd.to_datetime(ventas_df["Fecha"])
    ventas_df["Mes"] = ventas_df["Fecha"].dt.to_period("M").astype(str)
    ventas_prod = ventas_df.groupby("Producto")["PrecioVenta"].sum().sort_values(ascending=False)
    st.bar_chart(ventas_prod)

st.markdown("---")

# =========================
# Tabs principales
# =========================
tab_inv, tab_sales, tab_exp, tab_crm, tab_sup, tab_reports, tab_cf, tab_results = st.tabs(
    ["🗃️ Inventario", "🧾 Ventas", "💸 Gastos", "👥 Clientes", "🏭 Proveedores", "📊 Reportes", "💵 Flujo de caja", "📈 Estado de resultados"]
)

# =========================
# Inventario
# =========================
with tab_inv:
    st.subheader("Agregar producto")
    tipo = st.selectbox("Tipo de producto", TIPOS_PRODUCTO, key="inv_tipo")
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

    stocks_por_talla = {}
    stock_otro = None
    if tipo == "Zapatillas":
        st.markdown("#### Stock por talla (zapatillas)")
        cols = st.columns(6)
        for idx, t in enumerate(TALLAS_ZAPATILLAS):
            with cols[idx % 6]:
                stocks_por_talla[t] = st.number_input(f"Talla {t}", min_value=0, value=0, step=1, key=f"inv_tz_{t}")
    elif tipo == "Ropa":
        st.markdown("#### Stock por talla (ropa)")
        cols = st.columns(5)
        for idx, t in enumerate(TALLAS_ROPA):
            with cols[idx % 5]:
                stocks_por_talla[t] = st.number_input(f"Talla {t}", min_value=0, value=0, step=1, key=f"inv_tr_{t}")
    else:
        st.markdown("#### Stock para otro producto (sin tallas)")
        stock_otro = st.number_input("Stock total", min_value=0, value=0, step=1, key="inv_stock_otro")

    if st.button("Agregar producto", type="primary", key="inv_add"):
        if nombre and tipo:
            add_product(tipo, nombre, codigo, categoria, proveedor, precio, costo, stocks_por_talla, stock_otro)
        else:
            st.error("Ingresa el nombre y tipo de producto.")

    st.divider()
    st.subheader("Inventario actual")

    # Filtros avanzados
    with st.expander("🔎 Filtros avanzados"):
        filtro_prov = st.multiselect("Proveedor", sorted(st.session_state.df_inventario["Proveedor"].dropna().unique().tolist()))
        filtro_cat = st.multiselect("Categoría", sorted(st.session_state.df_inventario["Categoría"].dropna().unique().tolist()))
        filtro_tipo = st.multiselect("Tipo de producto", TIPOS_PRODUCTO)
        stock_bajo = st.checkbox(f"Solo stock bajo (≤ {st.session_state.low_stock_threshold})")

    search_inv = st.text_input("Buscar texto libre (modelo, código, categoría, proveedor)", key="inv_search")
    inv_view = ensure_inventory_columns(st.session_state.df_inventario.copy())

    # Aplicar filtros
    if filtro_prov:
        inv_view = inv_view[inv_view["Proveedor"].isin(filtro_prov)]
    if filtro_cat:
        inv_view = inv_view[inv_view["Categoría"].isin(filtro_cat)]
    if filtro_tipo:
        inv_view = inv_view[inv_view["Tipo"].isin(filtro_tipo)]
    if stock_bajo:
        inv_view = inv_view[inv_view["StockTotal"] <= st.session_state.low_stock_threshold]
    if not inv_view.empty and search_inv:
        mask = np.column_stack([
            inv_view[col].astype(str).str.contains(search_inv, case=False, na=False)
            for col in ["Producto", "Código", "Categoría", "Proveedor"]
        ]).any(axis=1)
        inv_view = inv_view[mask]

    # Íconos según tipo de producto
    if not inv_view.empty:
        inv_view["Icono"] = inv_view["Tipo"].map({"Zapatillas": "👟", "Ropa": "👕", "Otro": "📦"})

    st.markdown("#### Editar tabla de inventario")
    edited_inv = st.data_editor(
        inv_view,
        num_rows="dynamic",
        use_container_width=True,
        key="inv_editor"
    )
    if st.button("Guardar cambios de inventario", key="inv_save"):
        edited_inv = ensure_inventory_columns(edited_inv)
        edited_inv["StockTotal"] = edited_inv.apply(compute_stock_total_row, axis=1)
        st.session_state.df_inventario = edited_inv.reset_index(drop=True)
        st.success("Inventario actualizado.")

    st.markdown("#### Eliminar filas de inventario")
    idx_to_delete = st.multiselect("Selecciona índices a eliminar", options=edited_inv.index.tolist(), key="inv_del_sel")
    if st.button("Eliminar seleccionados", key="inv_del_btn"):
        st.session_state.df_inventario = edited_inv.drop(idx_to_delete).reset_index(drop=True)
        st.success("Filas eliminadas del inventario.")

    # Alertas de stock bajo
    low_df = st.session_state.df_inventario[st.session_state.df_inventario["StockTotal"] <= st.session_state.low_stock_threshold]
    if low_df.empty:
        st.markdown("✅ No hay modelos con stock total bajo.")
    else:
        st.warning(f"⚠️ Stock total bajo (≤ {st.session_state.low_stock_threshold})")
        st.dataframe(low_df, use_container_width=True)

# =========================
# Ventas
# =========================
with tab_sales:
    st.subheader("Registrar venta múltiple")
    with st.form("venta_multiple_form", clear_on_submit=False):
        fecha_v = st.date_input("Fecha", datetime.today(), key="ventas_fecha")
        comprador = st.text_input("Nombre del comprador", key="ventas_comprador")

        num_items = st.number_input("Número de ítems", min_value=1, value=1, step=1, key="ventas_num_items")
        items = []
        for j in range(int(num_items)):
            st.markdown(f"##### Ítem {j+1}")
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            with c1:
                producto = st.selectbox(
                    f"Producto {j+1}",
                    st.session_state.df_inventario["Producto"].tolist(),
                    key=f"venta_prod_{j}"
                )
                tipo_prod = "-"
                if producto:
                    fila = st.session_state.df_inventario[st.session_state.df_inventario["Producto"] == producto]
                    if not fila.empty:
                        tipo_prod = fila.iloc[0]["Tipo"]
            with c2:
                if tipo_prod == "Zapatillas":
                    talla = st.selectbox(f"Talla {j+1}", TALLAS_ZAPATILLAS, key=f"venta_tz_{j}")
                elif tipo_prod == "Ropa":
                    talla = st.selectbox(f"Talla {j+1}", TALLAS_ROPA, key=f"venta_tr_{j}")
                else:
                    talla = st.text_input(f"Talla {j+1} (N/A para Otro)", value="-", key=f"venta_ot_{j}")
            with c3:
                cantidad = st.number_input(f"Cantidad {j+1}", min_value=1, value=1, step=1, key=f"venta_cant_{j}")
            with c4:
                precio_venta = st.number_input(f"Precio {j+1}", min_value=0.0, value=0.0, step=1000.0, key=f"venta_prec_{j}")

            items.append({
                "Producto": producto,
                "Tipo": tipo_prod,
                "Talla": talla if tipo_prod in ["Zapatillas", "Ropa"] else None,
                "Cantidad": cantidad,
                "PrecioVenta": precio_venta
            })

        submitted = st.form_submit_button("Registrar venta múltiple")
        if submitted:
            if not comprador:
                st.error("Ingresa el nombre del comprador.")
            else:
                ok = register_multi_sale(fecha_v, comprador, items)
                if ok:
                    st.success("Venta múltiple registrada.")

    st.divider()
    st.subheader("Historial de ventas")

    # Filtros avanzados
    with st.expander("🔎 Filtros avanzados"):
        filtro_cliente = st.multiselect("Cliente", sorted(st.session_state.df_ventas["Comprador"].dropna().unique().tolist()))
        filtro_prod = st.multiselect("Producto", sorted(st.session_state.df_ventas["Producto"].dropna().unique().tolist()))
        filtro_tipo = st.multiselect("Tipo de producto", TIPOS_PRODUCTO)

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
        if filtro_cliente:
            v_view = v_view[v_view["Comprador"].isin(filtro_cliente)]
        if filtro_prod:
            v_view = v_view[v_view["Producto"].isin(filtro_prod)]
        if filtro_tipo:
            v_view = v_view[v_view["Tipo"].isin(filtro_tipo)]
        if search_v:
            mask_v = v_view.apply(lambda r: search_v.lower() in str(r.values).lower(), axis=1)
            v_view = v_view[mask_v]

    st.markdown("#### Editar tabla de ventas (con reconciliación de stock)")
    edited_sales = st.data_editor(
        v_view,
        num_rows="dynamic",
        use_container_width=True,
        key="ventas_editor"
    )

    # Guardar cambios con reconciliación: revertimos todas las ventas antiguas al inventario, aplicamos las nuevas
    if st.button("Guardar cambios de ventas", key="ventas_save"):
        old_sales = st.session_state.df_ventas.copy()
        new_sales = edited_sales.reset_index(drop=True)

        # Revertir inventario con ventas antiguas (devolver stock)
        for _, sale in old_sales.iterrows():
            producto = sale["Producto"]
            tipo = sale["Tipo"]
            talla = sale["Talla"] if sale["Talla"] != "-" else None
            cantidad = int(sale["Cantidad"])
            increment_inventory_for_sale(producto, tipo, talla, cantidad)

        # Aplicar ventas nuevas (descontar stock)
        ok_all = True
        for _, sale in new_sales.iterrows():
            producto = sale["Producto"]
            tipo = sale["Tipo"]
            talla = sale["Talla"] if sale["Talla"] != "-" else None
            cantidad = int(sale["Cantidad"])
            precio = float(sale["PrecioVenta"])
            # Recalcular comisión
            comision_pct = st.session_state.comision_pasarela / 100.0
            sale["Comision"] = float(precio) * comision_pct
            # Descontar
            ok = decrement_inventory_for_sale(producto, tipo, talla, cantidad)
            if not ok:
                ok_all = False
                break

        if ok_all:
            st.session_state.df_ventas = new_sales
            st.success("Ventas actualizadas y stock reconciliado.")
        else:
            st.error("No se pudieron aplicar todas las ventas editadas. Se mantiene el estado anterior.")

    st.markdown("#### Eliminar filas de ventas (devuelve stock)")
    idx_v_del = st.multiselect("Selecciona índices a eliminar (ventas)", options=edited_sales.index.tolist(), key="ventas_del_sel")
    if st.button("Eliminar ventas seleccionadas", key="ventas_del_btn"):
        # Devolver stock de las ventas eliminadas
        for i in idx_v_del:
            sale = edited_sales.loc[i]
            producto = sale["Producto"]
            tipo = sale["Tipo"]
            talla = sale["Talla"] if sale["Talla"] != "-" else None
            cantidad = int(sale["Cantidad"])
            increment_inventory_for_sale(producto, tipo, talla, cantidad)
        # Eliminar del DF de ventas
        st.session_state.df_ventas = edited_sales.drop(idx_v_del).reset_index(drop=True)
        st.success("Ventas eliminadas y stock devuelto.")

# =========================
# Gastos
# =========================
with tab_exp:
    st.subheader("Registrar gasto")
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1:
        fecha_g = st.date_input("Fecha del gasto", datetime.today(), key="gastos_fecha")
    with c2:
        tipo_g = st.selectbox("Tipo", ["Marketing","Envíos","Costos directos de producto","Shopify mensual","Otros"], key="gastos_tipo")
    with c3:
        monto = st.number_input("Monto", min_value=0.0, value=0.0, step=1000.0, key="gastos_monto")
    with c4:
        nota = st.text_input("Nota (opcional)", key="gastos_nota")
    if st.button("Agregar gasto", key="gastos_add"):
        add_expense(fecha_g, tipo_g, monto, nota)
        st.success("Gasto registrado.")

    st.divider()
    st.subheader("Historial de gastos")

    # Filtros avanzados
    with st.expander("🔎 Filtros avanzados"):
        filtro_tipo = st.multiselect("Tipo de gasto", sorted(st.session_state.df_gastos["Tipo"].dropna().unique().tolist()))
        search_g = st.text_input("Buscar texto (tipo, nota)", key="gastos_search_adv")

    colg1, colg2, colg3 = st.columns([2,1,1])
    with colg1:
        search_g_simple = st.text_input("Buscar (simple)", key="gastos_search")
    with colg2:
        g_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="gastos_desde")
    with colg3:
        g_fin = st.date_input("Hasta", value=datetime.today(), key="gastos_hasta")

    g_view = st.session_state.df_gastos.copy()
    if not g_view.empty:
        g_view["Fecha"] = pd.to_datetime(g_view["Fecha"])
        g_view = g_view[(g_view["Fecha"] >= pd.to_datetime(g_ini)) & (g_view["Fecha"] <= pd.to_datetime(g_fin))]
        if filtro_tipo:
            g_view = g_view[g_view["Tipo"].isin(filtro_tipo)]
        # búsquedas
        if search_g:
            mask_g_adv = g_view.apply(lambda r: search_g.lower() in str(r.values).lower(), axis=1)
            g_view = g_view[mask_g_adv]
        elif search_g_simple:
            mask_g = g_view.apply(lambda r: search_g_simple.lower() in str(r.values).lower(), axis=1)
            g_view = g_view[mask_g]

    st.markdown("#### Editar tabla de gastos")
    edited_exp = st.data_editor(
        g_view,
        num_rows="dynamic",
        use_container_width=True,
        key="gastos_editor"
    )
    if st.button("Guardar cambios de gastos", key="gastos_save"):
        st.session_state.df_gastos = edited_exp.reset_index(drop=True)
        st.success("Gastos actualizados.")

    st.markdown("#### Eliminar filas de gastos")
    idx_g_del = st.multiselect("Selecciona índices a eliminar (gastos)", options=edited_exp.index.tolist(), key="gastos_del_sel")
    if st.button("Eliminar gastos seleccionados", key="gastos_del_btn"):
        st.session_state.df_gastos = edited_exp.drop(idx_g_del).reset_index(drop=True)
        st.success("Gastos eliminados.")

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

# =========================
# Clientes (CRM)
# =========================
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

    st.markdown("#### Editar tabla de clientes")
    edited_cli = st.data_editor(
        st.session_state.df_clientes.copy(),
        num_rows="dynamic",
        use_container_width=True,
        key="cli_editor"
    )
    if st.button("Guardar cambios de clientes", key="cli_save"):
        st.session_state.df_clientes = edited_cli.reset_index(drop=True)
        st.success("Clientes actualizados.")

    st.markdown("#### Eliminar filas de clientes")
    idx_c_del = st.multiselect("Selecciona índices a eliminar (clientes)", options=edited_cli.index.tolist(), key="cli_del_sel")
    if st.button("Eliminar clientes seleccionados", key="cli_del_btn"):
        st.session_state.df_clientes = edited_cli.drop(idx_c_del).reset_index(drop=True)
        st.success("Clientes eliminados.")

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

# =========================
# Proveedores
# =========================
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

    st.markdown("#### Editar tabla de proveedores")
    edited_sup = st.data_editor(
        st.session_state.df_proveedores.copy(),
        num_rows="dynamic",
        use_container_width=True,
        key="sup_editor"
    )
    if st.button("Guardar cambios de proveedores", key="sup_save"):
        st.session_state.df_proveedores = edited_sup.reset_index(drop=True)
        st.success("Proveedores actualizados.")

    st.markdown("#### Eliminar filas de proveedores")
    idx_p_del = st.multiselect("Selecciona índices a eliminar (proveedores)", options=edited_sup.index.tolist(), key="sup_del_sel")
    if st.button("Eliminar proveedores seleccionados", key="sup_del_btn"):
        st.session_state.df_proveedores = edited_sup.drop(idx_p_del).reset_index(drop=True)
        st.success("Proveedores eliminados.")

# =========================
# Reportes
# =========================
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

# =========================
# Flujo de caja
# =========================
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

# =========================
# Estado de resultados
# =========================
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
    inv = ensure_inventory_columns(st.session_state.df_inventario.copy())

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
    costos_directos = 0.0
    if not sales_f.empty and not inv.empty and "CostoDirecto" in inv.columns:
        inv_cost = inv.set_index("Producto")["CostoDirecto"].to_dict()
        sales_f["CostoUnit"] = sales_f["Producto"].map(inv_cost).fillna(0.0)
        costos_directos = float((sales_f["CostoUnit"] * sales_f["Cantidad"]).sum())

    # Comisiones (solo pasarela)
    comisiones = float(sales_f["Comision"].sum()) if "Comision" in sales_f.columns else 0.0

    # Gastos
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

# =========================
# Exportación al final
# =========================
st.divider()
st.subheader("Exportar datos")
bytes_all_final = download_excel({
    "Inventario": ensure_inventory_columns(st.session_state.df_inventario.copy()),
    "Ventas": st.session_state.df_ventas.copy(),
    "Gastos": st.session_state.df_gastos.copy(),
    "Clientes": st.session_state.df_clientes.copy(),
    "Proveedores": st.session_state.df_proveedores.copy()
})
st.download_button("Descargar Excel (todos)", data=bytes_all_final, file_name="erp_zapatillas_todo.xlsx", key="export_excel_all_bottom")
