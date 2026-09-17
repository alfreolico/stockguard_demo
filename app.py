from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data import load_tables, sample_incoming_batch
from src.analytics import (
    filter_inventory,
    kpis,
    branch_performance,
    priority_schedule,
    diagnose_row,
    validate_batch,
)
from src.exporter import build_excel_report

st.set_page_config(page_title="StockGuard | Inventory Control & Analytics", page_icon="📦", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
.hero {border:1px solid rgba(128,128,128,.25); border-radius:18px; padding:1.1rem 1.2rem; margin-bottom:1rem; background:rgba(127,127,127,.035);}
.hero h1 {font-size:2rem; margin:0 0 .2rem 0;}
.muted {opacity:.72;}
.callout {border-left:4px solid #888; padding:.75rem 1rem; background:rgba(127,127,127,.05); border-radius:6px;}
div[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.2); padding:.7rem; border-radius:14px;}
</style>
""", unsafe_allow_html=True)

inventory, incidents_base, branches_df, products_df = load_tables()
if "incidents" not in st.session_state:
    st.session_state.incidents = incidents_base.copy()
if "batch" not in st.session_state:
    st.session_state.batch = sample_incoming_batch()

st.sidebar.title("StockGuard")
st.sidebar.caption("Inventory Control & Analytics")
page = st.sidebar.radio("Módulos", ["Dashboard", "Ingesta de datos", "Sucursales", "Investigación", "Rol de inventarios", "Incidencias", "Exportar reporte"])
st.sidebar.markdown("---")
st.sidebar.caption("Concept Demo · datos sintéticos · v0.1")

st.markdown("""
<div class="hero">
  <h1>StockGuard</h1>
  <div class="muted">Inventory Control & Analytics · cadena de abarrotes ficticia</div>
</div>
""", unsafe_allow_html=True)

min_date = inventory["inventory_date"].min().date()
max_date = inventory["inventory_date"].max().date()
with st.sidebar.expander("Filtros analíticos", expanded=True):
    date_range = st.date_input("Periodo", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    selected_branches = st.multiselect("Sucursal", sorted(inventory["branch_name"].unique()))
    selected_categories = st.multiselect("Categoría", sorted(inventory["category"].unique()))
    selected_leaders = st.multiselect("Líder", sorted(inventory["inventory_leader"].dropna().unique()))

filtered = filter_inventory(
    inventory,
    date_range=date_range if isinstance(date_range, (tuple, list)) and len(date_range) == 2 else None,
    branches=selected_branches,
    categories=selected_categories,
    leaders=selected_leaders,
)
base_df = filtered if not filtered.empty else inventory
incidents = st.session_state.incidents
branch_perf = branch_performance(base_df, incidents)
priority_full, visit_schedule = priority_schedule(branch_perf)
metrics = kpis(base_df, incidents)


def money(v):
    return f"${v:,.0f}"


if page == "Dashboard":
    st.subheader("Dashboard ejecutivo")
    st.caption("Vista consolidada de faltantes, exactitud, merma, a cobro e incidencias.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Faltantes", money(metrics["shortage"]))
    c2.metric("Exactitud", f"{metrics['accuracy']*100:.1f}%")
    c3.metric("Merma", money(metrics["shrinkage"]))
    c4.metric("A cobro", money(metrics["chargeable"]))
    c5.metric("Incidencias abiertas", metrics["open_incidents"])

    left, right = st.columns([1.25, 1])
    with left:
        top_shortage = base_df.groupby("branch_name", as_index=False)["shortage_value"].sum().sort_values("shortage_value", ascending=False).head(10)
        fig = px.bar(top_shortage, x="shortage_value", y="branch_name", orientation="h",
                     labels={"shortage_value":"Faltante $", "branch_name":"Sucursal"}, title="Top sucursales por faltante")
        fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=420)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        category_loss = base_df.groupby("category", as_index=False)["shortage_value"].sum().sort_values("shortage_value", ascending=False)
        fig2 = px.pie(category_loss, values="shortage_value", names="category", title="Concentración del faltante por categoría", hole=.45)
        fig2.update_layout(height=420)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### Atención prioritaria")
    display = branch_perf.head(8)[["branch_name","inventory_leader","accuracy","shortage_value","chargeable_amount","open_incidents"]].copy()
    display["accuracy"] = (display["accuracy"]*100).round(1).astype(str) + "%"
    display["shortage_value"] = display["shortage_value"].map(lambda x: f"${x:,.0f}")
    display["chargeable_amount"] = display["chargeable_amount"].map(lambda x: f"${x:,.0f}")
    display.columns = ["Sucursal","Líder","Exactitud","Faltante","A cobro","Incidencias"]
    st.dataframe(display, use_container_width=True, hide_index=True)

elif page == "Ingesta de datos":
    st.subheader("Ingesta y validación")
    st.write("Simula la recepción de información enviada por líderes de inventarios antes de integrarla a la base.")
    uploaded = st.file_uploader("Cargar archivo CSV o XLSX", type=["csv", "xlsx"])
    if uploaded is not None:
        try:
            batch = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
            st.session_state.batch = batch
            st.success(f"Archivo leído: {len(batch):,} filas.")
        except Exception as exc:
            st.error(f"No fue posible leer el archivo: {exc}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Generar lote de ejemplo", use_container_width=True):
            st.session_state.batch = sample_incoming_batch()
            st.rerun()
    with col_b:
        if st.button("Normalizar nombres de sucursal", use_container_width=True):
            b = st.session_state.batch.copy()
            if "branch_name" in b.columns:
                b["branch_name"] = b["branch_name"].astype(str).str.strip()
            st.session_state.batch = b
            st.rerun()

    batch = st.session_state.batch
    issues = validate_batch(batch)
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas recibidas", len(batch))
    c2.metric("Errores detectados", int(issues.loc[issues["severity"] == "ERROR", "count"].sum()) if not issues.empty else 0)
    c3.metric("Duplicados", int(batch.duplicated().sum()))
    st.markdown("#### Validaciones")
    st.dataframe(issues, use_container_width=True, hide_index=True)
    st.markdown("#### Vista previa del lote")
    st.dataframe(batch.head(20), use_container_width=True, hide_index=True)
    if st.button("Validar para carga"):
        blocking = int(issues.loc[issues["severity"] == "ERROR", "count"].sum()) if not issues.empty else 0
        if blocking:
            st.error(f"Lote bloqueado: existen {blocking} errores que deben corregirse.")
        else:
            st.success("Lote válido para carga a la base de datos.")

elif page == "Sucursales":
    st.subheader("Desempeño por sucursal")
    st.caption("Ranking para priorizar revisión operativa, no para sustituir la investigación.")
    table = branch_perf.copy()
    table["accuracy_pct"] = (table["accuracy"] * 100).round(2)
    fig = px.scatter(table, x="accuracy_pct", y="shortage_value", size="sales_amount", hover_name="branch_name", color="open_incidents",
                     labels={"accuracy_pct":"Exactitud %","shortage_value":"Faltante $","open_incidents":"Incidencias","sales_amount":"Ventas"},
                     title="Exactitud vs. faltante por sucursal")
    st.plotly_chart(fig, use_container_width=True)
    show = table[["branch_name","inventory_leader","accuracy_pct","shortage_value","shrinkage_value","chargeable_amount","open_incidents"]].copy()
    show.columns = ["Sucursal","Líder","Exactitud %","Faltante","Merma","A cobro","Incidencias"]
    st.dataframe(show, use_container_width=True, hide_index=True)

elif page == "Investigación":
    st.subheader("Investigación de discrepancias")
    st.caption("Selecciona una sucursal y un SKU con diferencia para investigar posibles causas.")
    branch_opts = sorted(inventory["branch_name"].unique())
    default_idx = branch_opts.index("Oriente") if "Oriente" in branch_opts else 0
    branch = st.selectbox("Sucursal", branch_opts, index=default_idx)
    data_branch = inventory[(inventory["branch_name"] == branch) & (inventory["difference_qty"] != 0)].copy()
    data_branch["label"] = data_branch["sku"].astype(str) + " · " + data_branch["product_name"].astype(str)
    sku_label = st.selectbox("SKU / Producto", data_branch["label"].drop_duplicates().tolist())
    sku = sku_label.split(" · ")[0]
    sku_hist = data_branch[data_branch["sku"].astype(str) == sku].sort_values("inventory_date")
    row = sku_hist.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock sistema", int(row["system_qty"]))
    c2.metric("Conteo físico", int(row["counted_qty"]))
    c3.metric("Diferencia", int(row["difference_qty"]))
    c4.metric("Impacto", money(row["shortage_value"]))
    cause, detail = diagnose_row(row)
    st.markdown(f"#### {cause}")
    st.markdown(f'<div class="callout">{detail}</div>', unsafe_allow_html=True)
    context = pd.DataFrame({"Indicador":["Ventas periodo","Entradas de compra","Merma registrada","Costo unitario","A cobro"],
                            "Valor":[int(row["sales_qty"]), int(row["purchase_entries"]), int(row["damaged_qty"]), f"${row['unit_cost']:,.2f}", f"${row['chargeable_amount']:,.2f}"]})
    st.markdown("#### Contexto operativo")
    st.dataframe(context, use_container_width=True, hide_index=True)
    st.markdown("#### Historial del SKU")
    st.dataframe(sku_hist[["inventory_date","difference_qty","shortage_value","sales_qty","purchase_entries"]], use_container_width=True, hide_index=True)

elif page == "Rol de inventarios":
    st.subheader("Rol de inventarios")
    st.caption("Propuesta de visitas basada en parámetros configurables de riesgo y operación.")
    st.markdown("**Priority Score v0.1:** 40% tiempo desde último inventario · 30% discrepancia · 20% ventas · 10% incidencias abiertas")
    rank = priority_full[["branch_name","inventory_leader","priority_score","accuracy","shortage_value","open_incidents"]].copy()
    rank["accuracy"] = (rank["accuracy"]*100).round(1)
    rank.columns = ["Sucursal","Líder","Prioridad","Exactitud %","Faltante","Incidencias"]
    st.dataframe(rank.head(12), use_container_width=True, hide_index=True)
    st.markdown("#### Próxima semana propuesta")
    sched = visit_schedule[["visit_day","visit_date","branch_name","inventory_leader","priority_score"]].copy()
    sched["visit_date"] = sched["visit_date"].dt.date
    sched.columns = ["Día","Fecha","Sucursal","Líder","Prioridad"]
    st.dataframe(sched, use_container_width=True, hide_index=True)

elif page == "Incidencias":
    st.subheader("Seguimiento de incidencias")
    st.caption("Control de sucesos reportados por líderes de inventario y control interno.")
    open_only = st.toggle("Mostrar sólo abiertas", value=True)
    view = incidents.copy()
    if open_only:
        view = view[~view["status"].isin(["RESOLVED","CLOSED"])]
    st.dataframe(view[["incident_id","branch_name","incident_type","priority","status","owner","created_at","description"]], use_container_width=True, hide_index=True)
    st.markdown("#### Registrar incidencia")
    with st.form("incident_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        branch_name = c1.selectbox("Sucursal", sorted(branches_df["branch_name"].unique()))
        incident_type = c2.selectbox("Tipo", ["Diferencia de inventario","Entrada de compra no conciliada","Merma pendiente","SKU sin homologar","Conteo incompleto","Otro"])
        priority = c1.selectbox("Prioridad", ["Alta","Media","Baja"])
        owner = c2.selectbox("Responsable", sorted(branches_df["inventory_leader"].unique()))
        desc = st.text_area("Descripción")
        if st.form_submit_button("Crear incidencia"):
            next_id = f"INC-{100 + len(st.session_state.incidents):04d}"
            new = pd.DataFrame([{
                "incident_id":next_id,
                "branch_id":branches_df.loc[branches_df["branch_name"] == branch_name, "branch_id"].iloc[0],
                "branch_name":branch_name,
                "incident_type":incident_type,
                "priority":priority,
                "status":"OPEN",
                "owner":owner,
                "created_at":pd.Timestamp("2026-09-16"),
                "description":desc or "Sin descripción.",
            }])
            st.session_state.incidents = pd.concat([st.session_state.incidents, new], ignore_index=True)
            st.success(f"Incidencia {next_id} creada.")

elif page == "Exportar reporte":
    st.subheader("Reportes y exportación")
    st.caption("Genera un Excel estructurado para análisis y seguimiento operativo.")
    st.write("Executive Summary · Branch Performance · Inventory Detail · Discrepancies · Shrinkage · Chargeable · Incidents · Visit Schedule")
    export = build_excel_report(metrics, branch_perf, base_df, incidents, visit_schedule)
    st.download_button("Descargar Inventory_Report.xlsx", data=export, file_name="Inventory_Report_2026-09.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.info("La exportación conserva filtros, encabezados, formatos básicos y hojas separadas para facilitar revisión en Excel.")
