from __future__ import annotations
import numpy as np
import pandas as pd


def filter_inventory(df, date_range=None, branches=None, categories=None, leaders=None):
    out = df.copy()
    if date_range and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out["inventory_date"] >= start) & (out["inventory_date"] <= end)]
    if branches:
        out = out[out["branch_name"].isin(branches)]
    if categories:
        out = out[out["category"].isin(categories)]
    if leaders:
        out = out[out["inventory_leader"].isin(leaders)]
    return out


def inventory_accuracy(df):
    denom = df["system_qty"].abs().sum()
    if denom == 0:
        return 1.0
    return max(0.0, 1 - (df["difference_qty"].abs().sum() / denom))


def kpis(df, incidents):
    open_inc = incidents[~incidents["status"].isin(["RESOLVED", "CLOSED"])]
    return {
        "shortage": float(df["shortage_value"].sum()),
        "shrinkage": float((df["damaged_qty"] * df["unit_cost"]).sum()),
        "accuracy": inventory_accuracy(df),
        "chargeable": float(df["chargeable_amount"].sum()),
        "open_incidents": int(len(open_inc)),
        "records": int(len(df)),
    }


def branch_performance(df, incidents):
    agg = df.groupby(["branch_id", "branch_name", "inventory_leader"], as_index=False).agg(
        system_qty=("system_qty", "sum"),
        abs_difference_qty=("difference_qty", lambda s: s.abs().sum()),
        shortage_value=("shortage_value", "sum"),
        sales_amount=("sales_amount", "sum"),
        chargeable_amount=("chargeable_amount", "sum"),
        last_inventory=("inventory_date", "max"),
    )
    shrink = df.assign(_shrink=df["damaged_qty"] * df["unit_cost"]).groupby("branch_id")["_shrink"].sum()
    agg["shrinkage_value"] = agg["branch_id"].map(shrink).fillna(0)
    agg["accuracy"] = (1 - agg["abs_difference_qty"] / agg["system_qty"].replace(0, np.nan)).clip(0, 1).fillna(1)
    open_inc = incidents[~incidents["status"].isin(["RESOLVED", "CLOSED"])]
    inc_counts = open_inc.groupby("branch_id").size()
    agg["open_incidents"] = agg["branch_id"].map(inc_counts).fillna(0).astype(int)
    return agg.sort_values(["accuracy", "shortage_value"], ascending=[True, False])


def priority_schedule(branch_df, reference_date=pd.Timestamp("2026-09-16")):
    df = branch_df.copy()
    df["days_since_last_inventory"] = (reference_date - pd.to_datetime(df["last_inventory"])).dt.days.clip(lower=0)

    def norm(s):
        s = s.astype(float)
        if s.max() == s.min():
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - s.min()) / (s.max() - s.min())

    discrepancy = 1 - df["accuracy"]
    df["priority_score"] = (
        0.40 * norm(df["days_since_last_inventory"]) +
        0.30 * norm(discrepancy) +
        0.20 * norm(df["sales_amount"]) +
        0.10 * norm(df["open_incidents"])
    ) * 100
    df["priority_score"] = df["priority_score"].round(1)
    top = df.sort_values("priority_score", ascending=False).head(5).copy()
    days_ahead = (7 - reference_date.weekday()) % 7 or 7
    monday = reference_date + pd.Timedelta(days=days_ahead)
    top["visit_date"] = [monday + pd.Timedelta(days=i) for i in range(len(top))]
    top["visit_day"] = top["visit_date"].dt.day_name().map({"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles","Thursday":"Jueves","Friday":"Viernes"})
    return df.sort_values("priority_score", ascending=False), top


def diagnose_row(row):
    diff = int(row["difference_qty"])
    if diff >= 0:
        return "Sin faltante", "La diferencia no representa faltante. Revisar sobreinventario si es material."
    shortage = abs(diff)
    purchases = int(row["purchase_entries"])
    sales = int(row["sales_qty"])
    damaged = int(row["damaged_qty"])
    if shortage >= 12 and purchases >= 25:
        return "Posible discrepancia en recepción/compras", "El faltante es material y existe volumen reciente de entradas. Conviene conciliar documento de recepción, captura y conteo."
    if damaged >= 3:
        return "Posible merma no conciliada", "Existe merma registrada relevante para el SKU. Revisar si toda la merma fue aplicada al inventario."
    if sales >= 90:
        return "Producto de alta rotación", "La alta salida incrementa el riesgo de desfase entre movimientos, captura y conteo. Revisar cortes y movimientos del periodo."
    return "Requiere investigación", "La diferencia no tiene una explicación determinística suficiente con los datos disponibles. Revisar movimientos, recepción, merma y conteo."


def validate_batch(batch):
    required = ["inventory_date","branch_id","branch_name","inventory_leader","sku","product_name","category","system_qty","counted_qty","unit_cost","sales_qty","purchase_entries","damaged_qty"]
    missing_cols = [c for c in required if c not in batch.columns]
    if missing_cols:
        return pd.DataFrame([{"severity":"ERROR","issue":"Columnas faltantes","count":len(missing_cols),"detail":", ".join(missing_cols)}])
    checks = [
        ("WARN", "Filas duplicadas", int(batch.duplicated().sum()), "Requieren deduplicación antes de carga."),
        ("ERROR", "SKU vacío", int(batch["sku"].astype(str).str.strip().isin(["", "nan", "None"]).sum()), "No se puede conciliar un registro sin SKU."),
        ("ERROR", "Stock de sistema negativo", int((pd.to_numeric(batch["system_qty"], errors="coerce") < 0).sum()), "Validar captura o movimiento previo."),
        ("WARN", "Líder no informado", int(batch["inventory_leader"].isna().sum()), "Completar responsable antes de publicar el lote."),
        ("INFO", "Nombre de sucursal con espacios", int((batch["branch_name"].astype(str) != batch["branch_name"].astype(str).str.strip()).sum()), "Se puede normalizar automáticamente."),
    ]
    return pd.DataFrame([{"severity":a,"issue":b,"count":c,"detail":d} for a,b,c,d in checks])
