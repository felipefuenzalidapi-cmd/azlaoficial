import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

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
            columns=["Fecha","Producto","Cantidad","Comprador","Talla","PrecioVenta"]
        )
    if "df_gastos" not in st.session_state:
        st.session_state.df_gastos = pd.DataFrame(columns=["Fecha","Tipo","Monto","Nota"])
    if "low_stock_threshold" not in st.session_state:
        st.session_state.low_stock_threshold = 5

init_state()

# ---------------- Funciones ----------------
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
        st.error("Producto no encontrado.")
        return False
    i = idx[0]
    stock_actual = int(inv.at[i, "Stock"])
    if cantidad <= 0:
        st.error("La cantidad debe ser mayor a 0.")
        return False
    if stock_actual < cantidad:
        st.warning(f"Stock insuficiente. Disponible {stock_actual}, solicitado {cantidad}.")
        return False
    inv.at[i, "Stock"] = stock_actual - cantidad
    st.session_state.df_inventario = inv

    sales = st.session_state.df_ventas.copy()
    new_sale = pd.DataFrame([{
        "Fecha": fecha.strftime("%Y-%m-%d"),
        "Producto": producto,
        "Cantidad": int(cantidad),
        "Comprador": comprador.strip(),
        "Talla": str(talla).strip(),
        "PrecioVenta": float(precio_venta)
    }])
    st.session_state.df_ventas = pd.concat([sales, new_sale], ignore_index=True)
    return True

def add_expense(fecha, tipo, monto, nota):
    exp = st.session_state.df_gastos.copy()
    new = pd.DataFrame([{
        "Fecha": fecha.strftime("%Y-%m-%d"),
        "Tipo": tipo,
        "Monto": float(monto),
        "Nota": (nota or "").strip()
    }])
    st.session_state.df_gastos = pd.concat([exp, new], ignore_index=True)

def download_excel(df_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in df_dict.items():
            df.to_excel(writer, sheet_name=name[:30], index=False)
    return output.getvalue()

# ---------------- Tabs principales ----------------
tab_inv, tab_sales, tab_exp, tab_results = st.tabs(
    ["🗃️ Inventario", "🧾 Ventas", "💸 Gastos", "📈 Estado de resultados"]
)

# ---------------- Inventario ----------------
with tab_inv:
    st.subheader("Agregar producto")
    nombre = st.text_input("Nombre", key="inv_nombre")
    codigo = st.text_input("Código", key="inv_codigo")
    categoria = st.text_input("Categoría", key="inv_categoria")
    proveedor = st.text_input("Proveedor", key="inv_proveedor")
    stock = st.number_input("Stock inicial", min_value=0, value=0, step=1, key="inv_stock")
    precio = st.number_input("Precio unitario (venta)", min_value=0.0, value=0.0, step=100.0, key="inv_precio")
    costo = st.number_input("Costo directo (unitario)", min_value=0.0, value=0.0, step=100.0, key="inv_costo")
    if st.button("Agregar producto", key="inv_add"):
        if nombre:
            add_product(nombre, codigo, categoria, stock, precio, costo, proveedor)
            st.success("Producto agregado.")
        else:
            st.error("Ingresa el nombre del producto.")

    st.divider()
    st.subheader("Inventario actual")
    search_inv = st.text_input("Buscar inventario", key="inv_search")
    inv_view = st.session_state.df_inventario.copy()
    if search_inv:
        mask = np.column_stack([
            inv_view[col].astype(str).str.contains(search_inv, case=False, na=False)
            for col in ["Producto","Código","Categoría","Proveedor"]
        ]).any(axis=1)
        inv_view = inv_view[mask]
    st.dataframe(inv_view, use_container_width=True)

    low_df = st.session_state.df_inventario[
        st.session_state.df_inventario["Stock"] <= st.session_state.low_stock_threshold
    ]
    if not low_df.empty:
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
        num_items = st.number_input("Número de productos", min_value=1, value=1, step=1, key="ventas_num_items")

        items = []
        for i in range(num_items):
            st.markdown(f"**Producto {i+1}**")
            producto = st.selectbox(
                f"Producto {i+1}", st.session_state.df_inventario["Producto"].tolist(), key=f"ventas_producto_{i}"
            )
            cantidad = st.number_input(
                f"Cantidad {i+1}", min_value=1, value=1, step=1, key=f"ventas_cantidad_{i}"
            )
            talla = st.text_input(f"Talla {i+1}", key=f"ventas_talla_{i}")
            precio_venta = st.number_input(
                f"Precio venta {i+1}", min_value=0.0, value=0.0, step=100.0, key=f"ventas_precio_{i}"
            )
            items.append({
                "Producto": producto,
                "Cantidad": cantidad,
                "Talla": talla,
                "PrecioVenta": precio_venta
            })

        if st.button("Registrar venta múltiple", key="ventas_registrar"):
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
    search_v = st.text_input("Buscar venta", key="ventas_search")
    v_view = st.session_state.df_ventas.copy()
    if search_v:
        mask = v_view.apply(lambda r: search_v.lower() in str(r.values).lower(), axis=1)
        v_view = v_view[mask]
    st.dataframe(v_view, use_container_width=True)

# ---------------- Gastos ----------------
with tab_exp:
    st.subheader("Registrar gasto")
    fecha_g = st.date_input("Fecha del gasto", datetime.today(), key="gastos_fecha")
    tipo = st.selectbox("Tipo", ["Marketing","Envíos","Costos directos de producto","Otros"], key="gastos_tipo")
    monto = st.number_input("Monto", min_value=0.0, value=0.0, step=100.0, key="gastos_monto")
    nota = st.text_input("Nota", key="gastos_nota")
    if st.button("Agregar gasto", key="gastos_add"):
        add_expense(fecha_g, tipo, monto, nota)
        st.success("Gasto registrado.")

    st.divider()
    st.subheader("Historial de gastos")
    search_g = st.text_input("Buscar gasto", key="gastos_search")
    g_view = st.session_state.df_gastos.copy()
    if search_g:
        mask = g_view.apply(lambda r: search_g.lower() in str(r.values).lower(), axis=1)
        g_view = g_view[mask]
    st.dataframe(g_view, use_container_width=True)

# ---------------- Estado de resultados ----------------
with tab_results:
    st.subheader("Estado de resultados")
    er_ini = st.date_input("Desde", value=datetime.today().replace(day=1), key="er_desde")
    er_fin = st.date_input("Hasta", value=datetime.today(), key="er_hasta")

    sales = st.session_state.df_ventas.copy()
    exp = st.session_state.df_gastos.copy()

    # Ventas filtradas por fecha
    if not sales.empty:
        sales["Fecha"] = pd.to_datetime(sales["Fecha"])
        sales_f = sales[(sales["Fecha"] >= pd.to_datetime(er_ini)) & (sales["Fecha"] <= pd.to_datetime(er_fin))]
    else:
        sales_f = sales

    # Gastos filtrados por fecha
    if not exp.empty:
        exp["Fecha"] = pd.to_datetime(exp["Fecha"])
        exp_f = exp[(exp["Fecha"] >= pd.to_datetime(er_ini)) & (exp["Fecha"] <= pd.to_datetime(er_fin))]
    else:
        exp_f = exp

    ingresos = float(sales_f["PrecioVenta"].sum())
    gastos_totales = float(exp_f["Monto"].sum())
    resultado_neto = ingresos - gastos_totales
    margen_neto_pct = (resultado_neto / ingresos * 100) if ingresos > 0 else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ingresos", f"${ingresos:,.0f}")
    col2.metric("Gastos", f"${gastos_totales:,.0f}")
    col3.metric("Resultado neto", f"${resultado_neto:,.0f}")
    col4.metric("Margen neto %", f"{margen_neto_pct:.2f}%")

    st.divider()
    st.write("Detalle de ventas (filtrado)")
    st.dataframe(sales_f, use_container_width=True)
    st.write("Detalle de gastos (filtrado)")
    st.dataframe(exp_f, use_container_width=True)

# ---------------- Exportación ----------------
st.divider()
st.subheader("Exportar datos")
bytes_all = download_excel({
    "Inventario": st.session_state.df_inventario,
    "Ventas": st.session_state.df_ventas,
    "Gastos": st.session_state.df_gastos
})
st.download_button("Descargar Excel (todos)", data=bytes_all, file_name="erp_ligero.xlsx", key="export_excel_all")
