from __future__ import annotations

import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "stockguard_demo.db"

BRANCHES = [
    ("S001", "Centro", "Mérida", "Ana López"),
    ("S002", "Norte", "Mérida", "Carlos Méndez"),
    ("S003", "Oriente", "Mérida", "Carlos Méndez"),
    ("S004", "Poniente", "Mérida", "Ana López"),
    ("S005", "Sur", "Mérida", "Fernanda Ruiz"),
    ("S006", "Progreso", "Progreso", "Fernanda Ruiz"),
    ("S007", "Umán", "Umán", "Luis Pacheco"),
    ("S008", "Kanasín", "Kanasín", "Luis Pacheco"),
    ("S009", "Cholul", "Mérida", "Ana López"),
    ("S010", "Itzimná", "Mérida", "Ana López"),
    ("S011", "Altabrisa", "Mérida", "Carlos Méndez"),
    ("S012", "Francisco de Montejo", "Mérida", "Carlos Méndez"),
    ("S013", "Tixkokob", "Tixkokob", "Luis Pacheco"),
    ("S014", "Conkal", "Conkal", "Fernanda Ruiz"),
    ("S015", "Motul", "Motul", "Fernanda Ruiz"),
    ("S016", "Hunucmá", "Hunucmá", "Luis Pacheco"),
    ("S017", "Caucel", "Mérida", "Ana López"),
    ("S018", "Chuburná", "Mérida", "Ana López"),
    ("S019", "Pacabtún", "Mérida", "Carlos Méndez"),
    ("S020", "Juan Pablo II", "Mérida", "Carlos Méndez"),
]

CATEGORIES = ["Bebidas", "Lácteos", "Botanas", "Abarrotes", "Limpieza", "Higiene", "Congelados", "Panificación"]
PRODUCT_BASE = {
    "Bebidas": ["Refresco", "Agua", "Jugo", "Energética", "Té"],
    "Lácteos": ["Leche", "Yogurt", "Queso", "Crema", "Mantequilla"],
    "Botanas": ["Papas", "Galletas", "Cacahuates", "Palomitas", "Totopos"],
    "Abarrotes": ["Arroz", "Frijol", "Aceite", "Pasta", "Atún"],
    "Limpieza": ["Detergente", "Cloro", "Suavizante", "Limpiador", "Jabón"],
    "Higiene": ["Shampoo", "Pasta dental", "Papel higiénico", "Desodorante", "Toallas"],
    "Congelados": ["Helado", "Verduras", "Pizza", "Nuggets", "Hielo"],
    "Panificación": ["Pan caja", "Tortillas", "Tostadas", "Pan dulce", "Harina"],
}


def _product_catalog(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    sku_num = 7501000000000
    for category in CATEGORIES:
        names = PRODUCT_BASE[category]
        for i in range(18):
            rows.append({
                "sku": str(sku_num),
                "product_name": f"{names[i % len(names)]} {i+1:02d}",
                "category": category,
                "unit_cost": round(float(rng.uniform(8, 95)), 2),
                "unit_price": round(float(rng.uniform(15, 150)), 2),
            })
            sku_num += 1
    return pd.DataFrame(rows)


def _inventory_data(seed: int = 20260916) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    products = _product_catalog(seed)
    dates = pd.date_range("2026-04-01", periods=6, freq="MS") + pd.Timedelta(days=14)
    rows = []
    for branch_id, branch_name, city, leader in BRANCHES:
        branch_risk = {"Oriente": 1.9, "Norte": 1.4, "Umán": 1.2, "Kanasín": 1.25}.get(branch_name, 1.0)
        sample_products = products.sample(95, random_state=int(branch_id[1:]))
        for inv_date in dates:
            for _, p in sample_products.iterrows():
                system_qty = max(0, int(rng.normal(95, 35)))
                diff = int(np.round(rng.normal(-0.8 * branch_risk, 2.7 * branch_risk)))
                if branch_name == "Oriente" and p["category"] in ["Bebidas", "Lácteos"] and rng.random() < 0.09:
                    diff -= int(rng.integers(8, 25))
                counted_qty = max(0, system_qty + diff)
                sales_qty = max(0, int(rng.normal(70, 28)))
                purchase_entries = max(0, int(rng.normal(55, 22)))
                damaged_qty = max(0, int(rng.poisson(1.2 if p["category"] in ["Lácteos", "Panificación"] else 0.5)))
                diff_qty = counted_qty - system_qty
                diff_value = diff_qty * float(p["unit_cost"])
                shortage_value = abs(min(diff_value, 0))
                overage_value = max(diff_value, 0)
                allowed_amount = max(0, sales_qty * float(p["unit_price"]) * 0.012)
                chargeable_amount = max(0, shortage_value - allowed_amount)
                rows.append({
                    "inventory_date": inv_date.date().isoformat(),
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "city": city,
                    "inventory_leader": leader,
                    "sku": p["sku"],
                    "product_name": p["product_name"],
                    "category": p["category"],
                    "system_qty": system_qty,
                    "counted_qty": counted_qty,
                    "difference_qty": diff_qty,
                    "unit_cost": p["unit_cost"],
                    "unit_price": p["unit_price"],
                    "difference_value": round(diff_value, 2),
                    "shortage_value": round(shortage_value, 2),
                    "overage_value": round(overage_value, 2),
                    "sales_qty": sales_qty,
                    "sales_amount": round(sales_qty * float(p["unit_price"]), 2),
                    "purchase_entries": purchase_entries,
                    "damaged_qty": damaged_qty,
                    "allowed_amount": round(allowed_amount, 2),
                    "chargeable_amount": round(chargeable_amount, 2),
                })
    return pd.DataFrame(rows)


def _incidents(seed: int = 1818) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    types = ["Diferencia de inventario", "Entrada de compra no conciliada", "Merma pendiente", "SKU sin homologar", "Conteo incompleto"]
    rows = []
    base = pd.Timestamp("2026-09-01")
    for i in range(42):
        branch = BRANCHES[int(rng.integers(0, len(BRANCHES)))]
        rows.append({
            "incident_id": f"INC-{i+1:04d}",
            "branch_id": branch[0],
            "branch_name": branch[1],
            "incident_type": rng.choice(types),
            "priority": rng.choice(["Alta", "Media", "Baja"], p=[0.28, 0.47, 0.25]),
            "status": rng.choice(["OPEN", "INVESTIGATING", "ACTION REQUIRED", "RESOLVED", "CLOSED"], p=[0.22,0.26,0.16,0.22,0.14]),
            "owner": branch[3],
            "created_at": (base + pd.Timedelta(days=int(rng.integers(0, 15)))).date().isoformat(),
            "description": "Revisión requerida por diferencia detectada durante control de inventario.",
        })
    rows.append({
        "incident_id": "INC-0099", "branch_id": "S003", "branch_name": "Oriente",
        "incident_type": "Entrada de compra no conciliada", "priority": "Alta",
        "status": "INVESTIGATING", "owner": "Carlos Méndez", "created_at": "2026-09-14",
        "description": "Diferencia recurrente entre entrada registrada y conteo físico en categoría Bebidas.",
    })
    return pd.DataFrame(rows)


def ensure_database() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        return DB_PATH
    inventory = _inventory_data()
    incidents = _incidents()
    branches = pd.DataFrame(BRANCHES, columns=["branch_id", "branch_name", "city", "inventory_leader"])
    products = _product_catalog()
    with sqlite3.connect(DB_PATH) as conn:
        inventory.to_sql("inventory", conn, index=False, if_exists="replace")
        incidents.to_sql("incidents", conn, index=False, if_exists="replace")
        branches.to_sql("branches", conn, index=False, if_exists="replace")
        products.to_sql("products", conn, index=False, if_exists="replace")
    return DB_PATH


def load_tables():
    ensure_database()
    with sqlite3.connect(DB_PATH) as conn:
        inventory = pd.read_sql("SELECT * FROM inventory", conn)
        incidents = pd.read_sql("SELECT * FROM incidents", conn)
        branches = pd.read_sql("SELECT * FROM branches", conn)
        products = pd.read_sql("SELECT * FROM products", conn)
    inventory["inventory_date"] = pd.to_datetime(inventory["inventory_date"])
    incidents["created_at"] = pd.to_datetime(incidents["created_at"])
    return inventory, incidents, branches, products


def sample_incoming_batch(n: int = 45) -> pd.DataFrame:
    inv, *_ = load_tables()
    cols = ["inventory_date", "branch_id", "branch_name", "inventory_leader", "sku", "product_name", "category", "system_qty", "counted_qty", "unit_cost", "sales_qty", "purchase_entries", "damaged_qty"]
    batch = inv[cols].sample(n, random_state=77).copy().reset_index(drop=True)
    if len(batch) >= 6:
        batch.loc[0, "branch_name"] = " Oriente "
        batch.loc[1, "sku"] = ""
        batch.loc[2, "system_qty"] = -5
        batch.loc[3, "inventory_leader"] = None
        batch = pd.concat([batch, batch.iloc[[4]]], ignore_index=True)
    return batch
