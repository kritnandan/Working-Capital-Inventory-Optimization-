"""
Tool handler implementations for MCP SSE Server
Grouped by category: dashboard, inventory, cash_cycle, demand, supplier, files
Aligned with DATASETS.md — 9 interlinked tables.
"""

import os, json, math
import duckdb
from falkordb import FalkorDB

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))

def get_duckdb():
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    return duckdb.connect(DUCKDB_PATH)

def get_graph():
    return FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT).select_graph("supply_chain")

def has(conn, t):
    try: return t in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]
    except: return False

def cnt(conn, t):
    try: return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except: return 0

# Table aliases: DATASETS.md names
T_PRODUCTS = "products"
T_CUSTOMERS = "customers"
T_SUPPLIERS = "suppliers"
T_INVENTORY = "inventory_snapshot"
T_SALES = "sales_transactions"
T_PO = "purchase_orders"
T_AR = "ar_ledger"
T_AP = "ap_ledger"
T_SHIP = "shipments"

ALL_TABLES = [T_PRODUCTS, T_CUSTOMERS, T_SUPPLIERS, T_INVENTORY, T_SALES, T_PO, T_AR, T_AP, T_SHIP]

# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD & OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════

def handle_get_full_dashboard(args):
    conn = get_duckdb()
    d = {}
    if has(conn, T_SALES):
        r = conn.execute(f"SELECT SUM(total_revenue), SUM(total_cost), SUM(gross_profit), COUNT(*), COUNT(DISTINCT product_id) FROM {T_SALES}").fetchone()
        d["revenue"] = {"total_revenue": float(r[0] or 0), "total_cost": float(r[1] or 0), "gross_profit": float(r[2] or 0), "transactions": r[3], "unique_products": r[4]}
    if has(conn, T_INVENTORY):
        r = conn.execute(f"SELECT COUNT(DISTINCT product_id), SUM(qty_on_hand), SUM(inventory_value), SUM(CASE WHEN stock_status='stockout' THEN 1 ELSE 0 END), SUM(CASE WHEN stock_status='overstock' THEN 1 ELSE 0 END) FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})").fetchone()
        d["inventory"] = {"unique_skus": r[0], "total_units": int(r[1] or 0), "total_value": float(r[2] or 0), "stockouts": int(r[3] or 0), "overstocked": int(r[4] or 0)}
    if has(conn, T_SUPPLIERS):
        r = conn.execute(f"SELECT COUNT(*), ROUND(AVG(avg_lead_time_days),1), ROUND(AVG(on_time_delivery_rate),3) FROM {T_SUPPLIERS}").fetchone()
        d["suppliers"] = {"count": r[0], "avg_lead_time": float(r[1] or 0), "avg_otd_rate": float(r[2] or 0)}
    if has(conn, T_CUSTOMERS):
        r = conn.execute(f"SELECT COUNT(*), SUM(ytd_revenue), ROUND(AVG(avg_days_to_pay),1) FROM {T_CUSTOMERS}").fetchone()
        d["customers"] = {"count": r[0], "total_ytd_revenue": float(r[1] or 0), "avg_days_to_pay": float(r[2] or 0)}
    if has(conn, T_AR):
        r = conn.execute(f"SELECT COUNT(*), SUM(CASE WHEN is_overdue THEN 1 ELSE 0 END), SUM(CASE WHEN write_off_flag THEN invoice_amount ELSE 0 END) FROM {T_AR}").fetchone()
        d["ar"] = {"total_invoices": r[0], "overdue": int(r[1] or 0), "write_off_amount": float(r[2] or 0)}
    if has(conn, T_PO):
        r = conn.execute(f"SELECT COUNT(*), SUM(qty_ordered), SUM(total_po_value) FROM {T_PO}").fetchone()
        d["purchase_orders"] = {"count": r[0], "total_qty": int(r[1] or 0), "total_value": float(r[2] or 0)}
    conn.close()
    return d if d else {"message": "No data uploaded yet."}

def handle_get_kpi_summary(args):
    conn = get_duckdb()
    result = {"formula": "CCC = DIO + DSO - DPO", "unit": "days"}
    # DIO
    if has(conn, T_INVENTORY) and has(conn, T_SALES):
        try:
            inv = conn.execute(f"SELECT SUM(inventory_value) FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})").fetchone()
            cogs = conn.execute(f"SELECT SUM(total_cost), COUNT(DISTINCT transaction_date) FROM {T_SALES}").fetchone()
            daily_cogs = float(cogs[0] or 0) / max(int(cogs[1] or 1), 1)
            result["dio"] = round(float(inv[0] or 0) / daily_cogs, 1) if daily_cogs > 0 else 0
        except: result["dio"] = 0
    else: result["dio"] = 0; result["dio_note"] = "Need inventory_snapshot + sales_transactions"
    # DSO from AR
    if has(conn, T_AR):
        try:
            r = conn.execute(f"SELECT SUM(days_to_pay * invoice_amount) / NULLIF(SUM(invoice_amount), 0) FROM {T_AR} WHERE days_to_pay IS NOT NULL").fetchone()
            result["dso"] = round(float(r[0] or 0), 1)
        except: result["dso"] = 0
    else: result["dso"] = 30.0; result["dso_note"] = "Upload ar_ledger for real DSO"
    # DPO from AP
    if has(conn, T_AP):
        try:
            r = conn.execute(f"SELECT SUM(actual_days_to_pay * invoice_amount) / NULLIF(SUM(invoice_amount), 0) FROM {T_AP} WHERE actual_days_to_pay IS NOT NULL").fetchone()
            result["dpo"] = round(float(r[0] or 0), 1)
        except: result["dpo"] = 0
    else: result["dpo"] = 0; result["dpo_note"] = "Upload ap_ledger for real DPO"
    result["ccc"] = round(result["dio"] + result["dso"] - result["dpo"], 1)
    conn.close()
    return result

def handle_get_data_quality_report(args):
    conn = get_duckdb()
    report = {}
    for t in ALL_TABLES:
        if not has(conn, t): continue
        try:
            df = conn.execute(f"SELECT * FROM {t}").fetchdf()
            nulls = {c: int(df[c].isnull().sum()) for c in df.columns if df[c].isnull().sum() > 0}
            dupes = int(df.duplicated().sum())
            report[t] = {"rows": len(df), "columns": len(df.columns), "null_counts": nulls or "none",
                         "duplicate_rows": dupes, "quality_score": max(0, 100 - len(nulls)*5 - min(dupes,10)*2)}
        except Exception as e:
            report[t] = {"error": str(e)}
    conn.close()
    return report if report else {"message": "No data uploaded yet."}

# ═════════════════════════════════════════════════════════════════════════════
# INVENTORY MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

def handle_get_reorder_alerts(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    df = conn.execute(f"""
        SELECT product_id, location_id, qty_on_hand, reorder_point, safety_stock_target, stock_status, days_of_supply
        FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        AND qty_on_hand < reorder_point ORDER BY qty_on_hand ASC
    """).fetchdf()
    conn.close()
    return {"total_alerts": len(df), "alerts": df.to_dict("records")}

def handle_smart_reorder(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    limit = args.get("limit", 20)
    try:
        df = conn.execute(f"""
            SELECT i.product_id, i.qty_on_hand, i.reorder_point, i.days_of_supply,
                COALESCE(p.economic_order_qty, 100) as eoq,
                COALESCE(p.lead_time_days, 14) as lead_time,
                i.stock_status,
                CASE WHEN i.stock_status='stockout' THEN 1
                     WHEN i.stock_status='low_stock' THEN 2
                     ELSE 3 END as priority
            FROM {T_INVENTORY} i
            LEFT JOIN {T_PRODUCTS} p ON i.product_id=p.product_id
            WHERE i.snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
            AND i.qty_on_hand < i.reorder_point
            ORDER BY priority, i.days_of_supply ASC LIMIT {limit}
        """).fetchdf()
    except:
        df = conn.execute(f"SELECT product_id, qty_on_hand, reorder_point FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY}) AND qty_on_hand<reorder_point LIMIT {limit}").fetchdf()
    conn.close()
    return {"recommendations": df.to_dict("records"), "count": len(df)}

def handle_calculate_safety_stock(args):
    conn = get_duckdb()
    skus = args.get("skus", [])
    sl = args.get("service_level", 0.95)
    z = {0.90:1.28, 0.95:1.65, 0.99:2.33}.get(sl, 1.65)
    results = []
    for sku in skus[:20]:
        try:
            r = conn.execute(f"SELECT STDDEV(qty_sold), AVG(qty_sold) FROM {T_SALES} WHERE product_id='{sku}'").fetchone()
            sigma = float(r[0]) if r and r[0] else 50
            lt = 14
            if has(conn, T_PRODUCTS):
                lr = conn.execute(f"SELECT lead_time_days FROM {T_PRODUCTS} WHERE product_id='{sku}' LIMIT 1").fetchone()
                if lr and lr[0]: lt = int(lr[0])
            ss = round(z * sigma * (lt**0.5))
            results.append({"product_id": sku, "safety_stock": ss, "demand_std": round(sigma, 2), "lead_time": lt, "z_score": z})
        except Exception as e:
            results.append({"product_id": sku, "error": str(e)})
    conn.close()
    return {"formula": "SS = Z × σ_demand × √(Lead Time)", "service_level": f"{sl*100:.0f}%", "results": results}

def handle_calculate_eoq(args):
    conn = get_duckdb()
    skus = args.get("skus", [])
    S = args.get("order_cost", 50); h_pct = args.get("holding_cost_pct", 0.25)
    if not has(conn, T_SALES): conn.close(); return {"message": "Need sales_transactions data."}
    results = []
    for sku in skus[:20]:
        try:
            r = conn.execute(f"SELECT SUM(qty_sold), COUNT(DISTINCT transaction_date) FROM {T_SALES} WHERE product_id='{sku}'").fetchone()
            total_q, days = int(r[0] or 0), max(int(r[1] or 1), 1)
            annual = total_q / days * 365
            uc = conn.execute(f"SELECT unit_cost FROM {T_PRODUCTS} WHERE product_id='{sku}' LIMIT 1").fetchone() if has(conn, T_PRODUCTS) else None
            unit_cost = float(uc[0]) if uc and uc[0] else 10.0
            H = unit_cost * h_pct
            eoq = round(math.sqrt(2 * annual * S / H)) if H > 0 else 0
            results.append({"product_id": sku, "eoq": eoq, "annual_demand": round(annual), "unit_cost": unit_cost,
                           "orders_per_year": round(annual/eoq, 1) if eoq > 0 else 0})
        except Exception as e:
            results.append({"product_id": sku, "error": str(e)})
    conn.close()
    return {"formula": "EOQ = √(2DS/H)", "order_cost_S": S, "holding_pct_H": h_pct, "results": results}

def handle_inventory_turnover(args):
    conn = get_duckdb()
    if not has(conn, T_SALES) or not has(conn, T_INVENTORY): conn.close(); return {"message": "Need sales_transactions + inventory_snapshot."}
    limit = args.get("limit", 50)
    df = conn.execute(f"""
        SELECT i.product_id, i.qty_on_hand, i.unit_cost, i.inventory_value,
            COALESCE(s.total_sold,0) as total_sold, COALESCE(s.revenue,0) as revenue,
            CASE WHEN i.inventory_value>0 THEN ROUND(COALESCE(s.revenue,0)/i.inventory_value,2) ELSE 0 END as turnover_ratio
        FROM (SELECT product_id, SUM(qty_on_hand) as qty_on_hand, AVG(unit_cost) as unit_cost, SUM(inventory_value) as inventory_value
              FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY}) GROUP BY product_id) i
        LEFT JOIN (SELECT product_id, SUM(qty_sold) as total_sold, SUM(total_revenue) as revenue FROM {T_SALES} GROUP BY product_id) s ON i.product_id=s.product_id
        ORDER BY turnover_ratio DESC LIMIT {limit}
    """).fetchdf()
    conn.close()
    return {"skus": df.to_dict("records"), "count": len(df)}

def handle_inventory_aging(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    df = conn.execute(f"""
        SELECT product_id, SUM(qty_on_hand) as qty, SUM(inventory_value) as value, MAX(days_since_last_movement) as days_idle,
            CASE WHEN MAX(days_since_last_movement)<=30 THEN '0-30d'
                 WHEN MAX(days_since_last_movement)<=60 THEN '31-60d'
                 WHEN MAX(days_since_last_movement)<=90 THEN '61-90d'
                 ELSE '90+d' END as age_bucket
        FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        GROUP BY product_id
    """).fetchdf()
    conn.close()
    buckets = {}
    for b in ['0-30d','31-60d','61-90d','90+d']:
        sub = df[df['age_bucket']==b] if len(df) > 0 else df
        buckets[b] = {"sku_count": len(sub), "total_value": round(float(sub['value'].sum()), 2) if len(sub) > 0 else 0}
    return {"aging_buckets": buckets, "details": df.to_dict("records")}

def handle_dead_stock(args):
    conn = get_duckdb()
    days = args.get("days", 90)
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    df = conn.execute(f"""
        SELECT product_id, SUM(qty_on_hand) as qty, SUM(inventory_value) as value_at_risk,
            MAX(days_since_last_movement) as days_idle
        FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        GROUP BY product_id HAVING MAX(days_since_last_movement) > {days}
        ORDER BY value_at_risk DESC
    """).fetchdf()
    conn.close()
    return {"days_threshold": days, "items": len(df), "total_value_at_risk": round(float(df["value_at_risk"].sum()), 2) if len(df) > 0 else 0, "dead_stock": df.to_dict("records")}

def handle_overstock(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    df = conn.execute(f"""
        SELECT product_id, location_id, qty_on_hand, reorder_point, inventory_value, stock_status
        FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        AND stock_status='overstock' ORDER BY inventory_value DESC
    """).fetchdf()
    conn.close()
    return {"overstocked_items": len(df), "total_excess_value": round(float(df["inventory_value"].sum()), 2) if len(df) > 0 else 0, "items": df.to_dict("records")}

def handle_stockout_risk(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    horizon = args.get("horizon_days", 14)
    df = conn.execute(f"""
        SELECT product_id, location_id, qty_on_hand, days_of_supply, stock_status
        FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        AND days_of_supply < {horizon} AND days_of_supply >= 0
        ORDER BY days_of_supply ASC
    """).fetchdf()
    conn.close()
    return {"horizon_days": horizon, "at_risk_count": len(df), "items": df.to_dict("records")}

def handle_abc_xyz(args):
    conn = get_duckdb()
    if has(conn, T_PRODUCTS):
        df = conn.execute(f"SELECT product_id, product_name, category, abc_class, xyz_class, unit_cost, unit_price FROM {T_PRODUCTS} ORDER BY abc_class, xyz_class").fetchdf()
        conn.close()
        return {"total": len(df), "classification": df.to_dict("records"),
                "legend": {"A": "Top 80% revenue", "B": "Next 15%", "C": "Bottom 5%", "X": "Stable", "Y": "Variable", "Z": "Erratic"}}
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload products or sales_transactions."}
    limit = args.get("limit", 100)
    df = conn.execute(f"""
        WITH s AS (SELECT product_id, SUM(total_revenue) as rev, STDDEV(qty_sold) as std, AVG(qty_sold) as avg FROM {T_SALES} GROUP BY product_id),
        r AS (SELECT *, rev/SUM(rev) OVER()*100 as pct, SUM(rev) OVER(ORDER BY rev DESC)/SUM(rev) OVER()*100 as cum,
              CASE WHEN avg>0 THEN std/avg ELSE 0 END as cv FROM s)
        SELECT product_id, ROUND(rev,2) as revenue,
            CASE WHEN cum<=80 THEN 'A' WHEN cum<=95 THEN 'B' ELSE 'C' END as abc,
            CASE WHEN cv<0.5 THEN 'X' WHEN cv<1.0 THEN 'Y' ELSE 'Z' END as xyz
        FROM r ORDER BY rev DESC LIMIT {limit}
    """).fetchdf()
    conn.close()
    return {"total": len(df), "classification": df.to_dict("records")}

# ═════════════════════════════════════════════════════════════════════════════
# CASH CYCLE & WORKING CAPITAL
# ═════════════════════════════════════════════════════════════════════════════

def handle_simulate_ccc(args):
    conn = get_duckdb()
    dio_r, dso_r, dpo_i = args.get("dio_reduction", 0), args.get("dso_reduction", 0), args.get("dpo_increase", 0)
    annual_revenue = args.get("annual_revenue")
    if not annual_revenue and has(conn, T_SALES):
        try:
            r = conn.execute(f"SELECT SUM(total_revenue), COUNT(DISTINCT transaction_date) FROM {T_SALES}").fetchone()
            annual_revenue = (float(r[0] or 0) / max(int(r[1] or 1), 1)) * 365
        except: annual_revenue = 100000000
    annual_revenue = annual_revenue or 100000000
    conn.close()
    daily = annual_revenue / 365; total_saved = dio_r + dso_r + dpo_i
    return {"annual_revenue": round(annual_revenue, 2), "daily_revenue": round(daily, 2), "total_days_saved": total_saved,
            "total_cash_freed": round(total_saved * daily, 2),
            "breakdown": [{"action": f"Reduce DIO by {dio_r}d", "cash": round(dio_r*daily, 2)},
                          {"action": f"Reduce DSO by {dso_r}d", "cash": round(dso_r*daily, 2)},
                          {"action": f"Increase DPO by {dpo_i}d", "cash": round(dpo_i*daily, 2)}]}

def handle_working_capital_summary(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    df = conn.execute(f"""
        SELECT COALESCE(i.product_id,'unknown') as product_id,
            SUM(qty_on_hand) as total_units, SUM(inventory_value) as trapped_cash
        FROM {T_INVENTORY} i WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})
        GROUP BY product_id ORDER BY trapped_cash DESC LIMIT 50
    """).fetchdf()
    total = float(df["trapped_cash"].sum()) if len(df) > 0 else 0
    conn.close()
    return {"total_cash_trapped": round(total, 2), "top_items": df.to_dict("records")}

def handle_carrying_cost(args):
    conn = get_duckdb()
    if not has(conn, T_INVENTORY): conn.close(); return {"message": "Upload inventory_snapshot data."}
    h_pct = args.get("holding_cost_pct", 0.25)
    total = conn.execute(f"SELECT SUM(inventory_value) FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY})").fetchone()
    total_inv = float(total[0] or 0)
    conn.close()
    return {"total_inventory_value": round(total_inv, 2), "holding_rate": f"{h_pct*100}%",
            "annual_carrying_cost": round(total_inv * h_pct, 2), "monthly": round(total_inv * h_pct / 12, 2)}

def handle_pareto(args):
    conn = get_duckdb()
    dim = args.get("dimension", "revenue")
    if dim == "revenue":
        if not has(conn, T_SALES): conn.close(); return {"message": "No sales data."}
        df = conn.execute(f"WITH r AS (SELECT product_id, SUM(total_revenue) as val FROM {T_SALES} GROUP BY product_id ORDER BY val DESC) SELECT *, SUM(val) OVER(ORDER BY val DESC)/SUM(val) OVER()*100 as cum_pct FROM r").fetchdf()
    else:
        if not has(conn, T_INVENTORY): conn.close(); return {"message": "No inventory data."}
        df = conn.execute(f"WITH r AS (SELECT product_id, SUM(inventory_value) as val FROM {T_INVENTORY} WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM {T_INVENTORY}) GROUP BY product_id ORDER BY val DESC) SELECT *, SUM(val) OVER(ORDER BY val DESC)/SUM(val) OVER()*100 as cum_pct FROM r").fetchdf()
    conn.close()
    n = len(df); pct80 = len(df[df["cum_pct"] <= 80]) if n > 0 else 0
    return {"dimension": dim, "total_skus": n, "skus_driving_80pct": pct80,
            "pct_of_skus": round(pct80/n*100, 1) if n > 0 else 0, "pareto_data": df.head(50).to_dict("records")}

# ── NEW: AR Aging ─────────────────────────────────────────────────────────────
def handle_ar_aging(args):
    conn = get_duckdb()
    if not has(conn, T_AR): conn.close(); return {"message": "Upload ar_ledger data."}
    df = conn.execute(f"""
        SELECT aging_bucket, COUNT(*) as invoices, SUM(invoice_amount) as total_amount,
            SUM(CASE WHEN paid_date IS NULL THEN invoice_amount ELSE 0 END) as outstanding
        FROM {T_AR} GROUP BY aging_bucket
        ORDER BY CASE aging_bucket WHEN 'Current' THEN 0 WHEN '1-30 days' THEN 1 WHEN '31-60 days' THEN 2 WHEN '61-90 days' THEN 3 ELSE 4 END
    """).fetchdf()
    total_outstanding = conn.execute(f"SELECT SUM(invoice_amount) FROM {T_AR} WHERE paid_date IS NULL").fetchone()
    disputes = conn.execute(f"SELECT COUNT(*), SUM(invoice_amount) FROM {T_AR} WHERE dispute_flag=true").fetchone()
    writeoffs = conn.execute(f"SELECT COUNT(*), SUM(invoice_amount) FROM {T_AR} WHERE write_off_flag=true").fetchone()
    conn.close()
    return {"aging_buckets": df.to_dict("records"),
            "total_outstanding": float(total_outstanding[0] or 0),
            "disputes": {"count": int(disputes[0] or 0), "amount": float(disputes[1] or 0)},
            "write_offs": {"count": int(writeoffs[0] or 0), "amount": float(writeoffs[1] or 0)}}

# ── NEW: DSO Analysis ─────────────────────────────────────────────────────────
def handle_dso_analysis(args):
    conn = get_duckdb()
    if not has(conn, T_AR): conn.close(); return {"message": "Upload ar_ledger data."}
    weighted = conn.execute(f"SELECT SUM(days_to_pay * invoice_amount)/NULLIF(SUM(invoice_amount),0) FROM {T_AR} WHERE days_to_pay IS NOT NULL").fetchone()
    by_customer = conn.execute(f"""
        SELECT a.customer_id, c.customer_name, c.segment,
            ROUND(SUM(a.days_to_pay * a.invoice_amount)/NULLIF(SUM(a.invoice_amount),0),1) as weighted_dso,
            COUNT(*) as invoices, SUM(a.invoice_amount) as total_billed
        FROM {T_AR} a LEFT JOIN {T_CUSTOMERS} c ON a.customer_id=c.customer_id
        WHERE a.days_to_pay IS NOT NULL GROUP BY a.customer_id, c.customer_name, c.segment
        ORDER BY weighted_dso DESC LIMIT 20
    """).fetchdf() if has(conn, T_CUSTOMERS) else conn.execute(f"SELECT customer_id, ROUND(AVG(days_to_pay),1) as weighted_dso, COUNT(*) as invoices FROM {T_AR} WHERE days_to_pay IS NOT NULL GROUP BY customer_id ORDER BY weighted_dso DESC LIMIT 20").fetchdf()
    conn.close()
    return {"overall_dso": round(float(weighted[0] or 0), 1), "by_customer": by_customer.to_dict("records")}

# ── NEW: DPO Analysis ─────────────────────────────────────────────────────────
def handle_dpo_analysis(args):
    conn = get_duckdb()
    if not has(conn, T_AP): conn.close(); return {"message": "Upload ap_ledger data."}
    weighted = conn.execute(f"SELECT SUM(actual_days_to_pay * invoice_amount)/NULLIF(SUM(invoice_amount),0) FROM {T_AP}").fetchone()
    by_supplier = conn.execute(f"""
        SELECT a.supplier_id, s.supplier_name,
            ROUND(SUM(a.actual_days_to_pay * a.invoice_amount)/NULLIF(SUM(a.invoice_amount),0),1) as weighted_dpo,
            s.contracted_payment_days as terms, COUNT(*) as invoices,
            SUM(a.early_payment_discount) as total_discounts
        FROM {T_AP} a LEFT JOIN {T_SUPPLIERS} s ON a.supplier_id=s.supplier_id
        GROUP BY a.supplier_id, s.supplier_name, s.contracted_payment_days
        ORDER BY weighted_dpo DESC
    """).fetchdf() if has(conn, T_SUPPLIERS) else conn.execute(f"SELECT supplier_id, ROUND(AVG(actual_days_to_pay),1) as weighted_dpo, COUNT(*) as invoices FROM {T_AP} GROUP BY supplier_id ORDER BY weighted_dpo DESC").fetchdf()
    conn.close()
    return {"overall_dpo": round(float(weighted[0] or 0), 1), "by_supplier": by_supplier.to_dict("records")}

# ── NEW: Shipment Tracking ────────────────────────────────────────────────────
def handle_shipment_tracking(args):
    conn = get_duckdb()
    if not has(conn, T_SHIP): conn.close(); return {"message": "Upload shipments data."}
    status = args.get("status")
    where = f"WHERE status='{status}'" if status else ""
    df = conn.execute(f"""
        SELECT status, COUNT(*) as count, SUM(qty_shipped) as total_qty,
            SUM(freight_cost) as total_freight, ROUND(AVG(delay_days),1) as avg_delay
        FROM {T_SHIP} {where} GROUP BY status
    """).fetchdf()
    in_transit = conn.execute(f"SELECT shipment_id, supplier_id, product_id, ship_date, expected_arrival_date, qty_shipped, carrier FROM {T_SHIP} WHERE status='In Transit' LIMIT 20").fetchdf() if not status else None
    conn.close()
    result = {"summary": df.to_dict("records")}
    if in_transit is not None and len(in_transit) > 0:
        result["in_transit"] = in_transit.to_dict("records")
    return result

# ── NEW: Product Catalog ──────────────────────────────────────────────────────
def handle_product_catalog(args):
    conn = get_duckdb()
    if not has(conn, T_PRODUCTS): conn.close(); return {"message": "Upload products data."}
    category = args.get("category")
    abc = args.get("abc_class")
    where = []
    if category: where.append(f"category='{category}'")
    if abc: where.append(f"abc_class='{abc}'")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    df = conn.execute(f"SELECT * FROM {T_PRODUCTS} {clause} ORDER BY product_id").fetchdf()
    conn.close()
    return {"total": len(df), "products": df.to_dict("records")}

# ═════════════════════════════════════════════════════════════════════════════
# DEMAND & SALES ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════

def handle_forecast_demand(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    sku = args["sku"]; horizon = args.get("horizon_days", 30); window = args.get("window", 7)
    df = conn.execute(f"SELECT transaction_date as date, SUM(qty_sold) as daily_qty FROM {T_SALES} WHERE product_id='{sku}' GROUP BY transaction_date ORDER BY date").fetchdf()
    conn.close()
    if len(df) == 0: return {"message": f"No sales for '{sku}'."}
    values = df["daily_qty"].tolist()
    if len(values) < window: window = max(1, len(values))
    ma = sum(values[-window:]) / window
    trend = "stable"
    if len(values) >= window * 2:
        old_ma = sum(values[-window*2:-window]) / window
        if ma > old_ma * 1.1: trend = "increasing"
        elif ma < old_ma * 0.9: trend = "decreasing"
    return {"product_id": sku, "historical_days": len(values), "window": window, "trend": trend,
            "moving_average": round(ma, 2), "total_predicted": round(ma * horizon, 0)}

def handle_detect_anomalies(args):
    conn = get_duckdb()
    table = args.get("table", T_SALES); col = args.get("column", "qty_sold"); z_thresh = args.get("z_threshold", 2.0)
    if not has(conn, table): conn.close(); return {"message": f"No {table} data."}
    try:
        df = conn.execute(f"SELECT *, ({col} - AVG({col}) OVER()) / NULLIF(STDDEV({col}) OVER(), 0) as z_score FROM {table}").fetchdf()
        anomalies = df[abs(df["z_score"]) > z_thresh] if len(df) > 0 else df
        conn.close()
        return {"table": table, "column": col, "z_threshold": z_thresh,
                "total_rows": len(df), "anomalies_found": len(anomalies), "anomalies": anomalies.head(50).to_dict("records")}
    except Exception as e:
        conn.close(); return {"error": str(e)}

def handle_revenue_trends(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    gran = args.get("granularity", "monthly")
    trunc = {"daily": "transaction_date", "weekly": "DATE_TRUNC('week', transaction_date)"}.get(gran, "DATE_TRUNC('month', transaction_date)")
    df = conn.execute(f"SELECT {trunc} as period, SUM(total_revenue) as revenue, SUM(qty_sold) as units, COUNT(DISTINCT product_id) as skus FROM {T_SALES} GROUP BY period ORDER BY period").fetchdf()
    conn.close()
    records = df.to_dict("records")
    for i in range(1, len(records)):
        prev = records[i-1]["revenue"]
        records[i]["growth_pct"] = round((records[i]["revenue"] - prev) / prev * 100, 1) if prev > 0 else 0
    return {"granularity": gran, "periods": len(records), "trends": records}

def handle_sales_velocity(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    limit = args.get("limit", 30)
    df = conn.execute(f"""
        SELECT product_id, SUM(qty_sold) as total_sold, COUNT(DISTINCT transaction_date) as sale_days,
            ROUND(SUM(qty_sold)/NULLIF(COUNT(DISTINCT transaction_date),1), 2) as daily_velocity,
            SUM(total_revenue) as total_revenue
        FROM {T_SALES} GROUP BY product_id ORDER BY daily_velocity DESC LIMIT {limit}
    """).fetchdf()
    conn.close()
    return {"fastest_movers": df.to_dict("records"), "count": len(df)}

def handle_top_skus(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    limit = args.get("limit", 20)
    df = conn.execute(f"SELECT product_id, SUM(total_revenue) as revenue, SUM(qty_sold) as units, SUM(gross_profit) as profit FROM {T_SALES} GROUP BY product_id ORDER BY revenue DESC LIMIT {limit}").fetchdf()
    conn.close()
    return {"top_skus": df.to_dict("records"), "count": len(df)}

def handle_customer_concentration(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    limit = args.get("limit", 10)
    df = conn.execute(f"""
        SELECT s.customer_id, COALESCE(c.customer_name, s.customer_id) as customer_name,
            SUM(s.total_revenue) as revenue,
            SUM(s.total_revenue)/SUM(SUM(s.total_revenue)) OVER()*100 as revenue_pct,
            COUNT(DISTINCT s.product_id) as unique_products
        FROM {T_SALES} s LEFT JOIN {T_CUSTOMERS} c ON s.customer_id=c.customer_id
        GROUP BY s.customer_id, c.customer_name ORDER BY revenue DESC LIMIT {limit}
    """).fetchdf() if has(conn, T_CUSTOMERS) else conn.execute(f"SELECT customer_id, SUM(total_revenue) as revenue FROM {T_SALES} WHERE customer_id IS NOT NULL GROUP BY customer_id ORDER BY revenue DESC LIMIT {limit}").fetchdf()
    conn.close()
    top_pct = float(df["revenue_pct"].sum()) if "revenue_pct" in df.columns and len(df) > 0 else 0
    return {"top_customers": df.to_dict("records"), "concentration_risk": "high" if top_pct > 80 else "medium" if top_pct > 50 else "low"}

def handle_seasonality(args):
    conn = get_duckdb()
    if not has(conn, T_SALES): conn.close(); return {"message": "Upload sales_transactions data."}
    sku_filter = f"WHERE product_id='{args['sku']}'" if args.get("sku") else ""
    df = conn.execute(f"SELECT EXTRACT(MONTH FROM transaction_date) as month, SUM(qty_sold) as qty, SUM(total_revenue) as revenue FROM {T_SALES} {sku_filter} GROUP BY month ORDER BY month").fetchdf()
    conn.close()
    if len(df) == 0: return {"message": "Not enough data."}
    avg = float(df["qty"].mean())
    records = df.to_dict("records")
    for r in records: r["index_vs_avg"] = round(r["qty"]/avg, 2) if avg > 0 else 0
    peak = max(records, key=lambda x: x["qty"]); low = min(records, key=lambda x: x["qty"])
    return {"monthly_pattern": records, "peak_month": int(peak["month"]), "low_month": int(low["month"])}

# ═════════════════════════════════════════════════════════════════════════════
# SUPPLIER & GRAPH TOOLS
# ═════════════════════════════════════════════════════════════════════════════

def handle_supplier_risk_scores(args):
    conn = get_duckdb()
    if not has(conn, T_SUPPLIERS): conn.close(); return {"message": "Upload suppliers data."}
    df = conn.execute(f"SELECT * FROM {T_SUPPLIERS}").fetchdf()
    conn.close()
    results = []
    for _, r in df.iterrows():
        lt_score = min(100, max(0, (float(r.get("avg_lead_time_days", 14)) - 5) * 3))
        otd_score = max(0, (1 - float(r.get("on_time_delivery_rate", 0.9))) * 200)
        qrr_score = float(r.get("quality_rejection_rate", 0.01)) * 1000
        risk = round(lt_score * 0.3 + otd_score * 0.4 + qrr_score * 0.3, 1)
        results.append({"supplier_id": r["supplier_id"], "supplier_name": r["supplier_name"],
                        "risk_score": risk, "risk_level": "high" if risk > 60 else "medium" if risk > 30 else "low",
                        "lead_time": r.get("avg_lead_time_days"), "otd_rate": r.get("on_time_delivery_rate"), "qrr": r.get("quality_rejection_rate")})
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"suppliers": results}

def handle_supplier_performance(args):
    conn = get_duckdb()
    if not has(conn, T_SUPPLIERS): conn.close(); return {"message": "Upload suppliers data."}
    df = conn.execute(f"SELECT * FROM {T_SUPPLIERS} ORDER BY on_time_delivery_rate DESC").fetchdf()
    conn.close()
    return {"suppliers": df.to_dict("records"), "count": len(df)}

def handle_supplier_concentration(args):
    conn = get_duckdb()
    if not has(conn, T_PO): conn.close(); return {"message": "Upload purchase_orders data."}
    df = conn.execute(f"""
        SELECT supplier_id, COUNT(*) as orders, SUM(total_po_value) as total_value,
            SUM(total_po_value)*100.0/SUM(SUM(total_po_value)) OVER() as value_pct
        FROM {T_PO} GROUP BY supplier_id ORDER BY total_value DESC
    """).fetchdf()
    conn.close()
    top_pct = float(df.head(3)["value_pct"].sum()) if len(df) > 0 else 0
    return {"suppliers": df.to_dict("records"), "top3_value_pct": round(top_pct, 1),
            "concentration_risk": "high" if top_pct > 80 else "medium" if top_pct > 50 else "low"}

def _graph_tool(handler):
    try: return handler()
    except Exception as e: return {"message": f"Graph not populated: {str(e)}. Upload supplier/PO data."}

def handle_supplier_network(args):
    def _run():
        g = get_graph()
        r = g.query("MATCH (s:Supplier)-[:SUPPLIES]->(p:Product) RETURN s.supplier_id, s.supplier_name, s.lead_time, p.product_id ORDER BY s.supplier_name")
        return {"relationships": len(r.result_set), "network": [{"supplier_id": x[0], "supplier_name": x[1], "lead_time": x[2], "product_id": x[3]} for x in r.result_set]}
    result = _graph_tool(_run)
    if "message" in result and has(get_duckdb(), T_SUPPLIERS):
        conn = get_duckdb(); df = conn.execute(f"SELECT * FROM {T_SUPPLIERS}").fetchdf(); conn.close()
        return {"note": "Graph not populated, showing DuckDB.", "suppliers": df.to_dict("records")}
    return result

def handle_single_source(args):
    def _run():
        g = get_graph()
        r = g.query(f"MATCH (p:Product)<-[:SUPPLIES]-(s:Supplier) WITH p, COUNT(s) as c, COLLECT(s.supplier_name) as sups WHERE c=1 RETURN p.product_id, sups[0] LIMIT {args.get('limit', 50)}")
        return {"total": len(r.result_set), "risks": [{"product_id": x[0], "sole_supplier": x[1], "risk": "high"} for x in r.result_set]}
    return _graph_tool(_run)

def handle_ripple(args):
    sid = args.get("supplier_id", "")
    def _run():
        g = get_graph()
        r = g.query(f"MATCH (s:Supplier {{supplier_id:'{sid}'}})-[:SUPPLIES]->(p:Product) RETURN s.supplier_name, p.product_id")
        if not r.result_set: return {"message": f"Supplier '{sid}' not found."}
        return {"supplier": r.result_set[0][0], "impacted": [x[1] for x in r.result_set], "count": len(r.result_set),
                "severity": "high" if len(r.result_set) > 10 else "medium" if len(r.result_set) > 3 else "low"}
    return _graph_tool(_run)

def handle_lead_time_var(args):
    def _run():
        g = get_graph()
        r = g.query("MATCH (s:Supplier) RETURN s.supplier_id, s.supplier_name, s.lead_time, s.rating ORDER BY s.lead_time DESC")
        return {"suppliers": [{"id": x[0], "name": x[1], "lead_time": x[2], "rating": x[3]} for x in r.result_set]}
    result = _graph_tool(_run)
    if "message" in result:
        conn = get_duckdb()
        if has(conn, T_SUPPLIERS):
            df = conn.execute(f"SELECT supplier_id, supplier_name, avg_lead_time_days, risk_score FROM {T_SUPPLIERS} ORDER BY avg_lead_time_days DESC").fetchdf()
            conn.close(); return {"note": "From DuckDB.", "suppliers": df.to_dict("records")}
        conn.close()
    return result

def handle_find_alternatives(args):
    sku = args.get("sku", "")
    def _run():
        g = get_graph()
        cur = g.query(f"MATCH (s:Supplier)-[:SUPPLIES]->(p:Product {{product_id:'{sku}'}}) RETURN s.supplier_id, s.supplier_name, s.lead_time")
        current = {"id": cur.result_set[0][0], "name": cur.result_set[0][1], "lead_time": cur.result_set[0][2]} if cur.result_set else None
        alt = g.query(f"MATCH (s:Supplier) WHERE NOT (s)-[:SUPPLIES]->({{product_id:'{sku}'}}) RETURN s.supplier_id, s.supplier_name, s.lead_time, s.rating ORDER BY s.rating DESC LIMIT 5")
        return {"product_id": sku, "current": current, "alternatives": [{"id": x[0], "name": x[1], "lead_time": x[2], "rating": x[3]} for x in alt.result_set]}
    return _graph_tool(_run)

# ═════════════════════════════════════════════════════════════════════════════
# FILE & DATA TOOLS
# ═════════════════════════════════════════════════════════════════════════════

def handle_list_uploads(args):
    conn = get_duckdb()
    files = []
    for cat in ALL_TABLES:
        if has(conn, cat):
            dest = "DuckDB + FalkorDB" if cat in ["suppliers", "purchase_orders"] else "DuckDB"
            files.append({"category": cat, "status": "uploaded", "rows": cnt(conn, cat), "destination": dest})
        else:
            files.append({"category": cat, "status": "not_uploaded"})
    conn.close()
    return {"files": files}

def handle_schema_info(args):
    conn = get_duckdb()
    t = args.get("table", "sales_transactions")
    if not has(conn, t): conn.close(); return {"message": f"Table '{t}' not uploaded yet. Valid tables: {ALL_TABLES}"}
    schema = conn.execute(f"DESCRIBE {t}").fetchdf()
    sample = conn.execute(f"SELECT * FROM {t} LIMIT 5").fetchdf()
    n = cnt(conn, t); conn.close()
    return {"table": t, "rows": n, "columns": schema.to_dict("records"), "sample": sample.to_dict("records")}

def handle_run_sql(args):
    sql = args.get("sql", "").strip()
    for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]:
        if kw in sql.upper(): return {"error": f"Write operations blocked: {kw}"}
    conn = get_duckdb(); df = conn.execute(sql).fetchdf(); conn.close()
    return {"rows": len(df), "columns": list(df.columns), "data": df.head(100).to_dict("records")}

def handle_version_history(args):
    conn = get_duckdb()
    if not has(conn, "file_uploads"):
        history = [{"category": t, "rows": cnt(conn, t), "status": "uploaded"} for t in ALL_TABLES if has(conn, t)]
        conn.close()
        return {"history": history} if history else {"message": "No data uploaded yet."}
    df = conn.execute("SELECT * FROM file_uploads ORDER BY upload_timestamp DESC").fetchdf()
    conn.close()
    return {"total_uploads": len(df), "history": df.to_dict("records")}

def handle_database_refresh(args):
    conn = get_duckdb()
    report = {"duckdb": {}, "falkordb": {}}
    for t in ALL_TABLES:
        if has(conn, t):
            report["duckdb"][t] = {"status": "ok", "rows": cnt(conn, t), "columns": len(conn.execute(f"DESCRIBE {t}").fetchall())}
        else:
            report["duckdb"][t] = {"status": "not_loaded"}
    conn.close()
    try:
        g = get_graph()
        s = g.query("MATCH (s:Supplier) RETURN COUNT(s)").result_set
        p = g.query("MATCH (p:Product) RETURN COUNT(p)").result_set
        r = g.query("MATCH ()-[r:SUPPLIES]->() RETURN COUNT(r)").result_set
        report["falkordb"] = {"status": "connected", "suppliers": s[0][0] if s else 0, "products": p[0][0] if p else 0, "relationships": r[0][0] if r else 0}
    except Exception as e:
        report["falkordb"] = {"status": "unavailable", "error": str(e)}
    return report

# ═════════════════════════════════════════════════════════════════════════════
# ROUTING MAP
# ═════════════════════════════════════════════════════════════════════════════

TOOL_MAP = {
    # Dashboard
    "get_full_dashboard": handle_get_full_dashboard,
    "get_kpi_summary": handle_get_kpi_summary,
    "get_data_quality_report": handle_get_data_quality_report,
    # Inventory
    "get_reorder_alerts": handle_get_reorder_alerts,
    "get_smart_reorder_recommendations": handle_smart_reorder,
    "calculate_safety_stock": handle_calculate_safety_stock,
    "calculate_eoq": handle_calculate_eoq,
    "get_inventory_turnover": handle_inventory_turnover,
    "get_inventory_aging": handle_inventory_aging,
    "get_dead_stock": handle_dead_stock,
    "get_overstock_analysis": handle_overstock,
    "get_stockout_risk": handle_stockout_risk,
    "get_abc_xyz_classification": handle_abc_xyz,
    # Cash Cycle
    "simulate_ccc_improvement": handle_simulate_ccc,
    "get_working_capital_summary": handle_working_capital_summary,
    "get_carrying_cost_analysis": handle_carrying_cost,
    "get_pareto_analysis": handle_pareto,
    "get_ar_aging": handle_ar_aging,
    "get_dso_analysis": handle_dso_analysis,
    "get_dpo_analysis": handle_dpo_analysis,
    # Demand & Sales
    "forecast_demand": handle_forecast_demand,
    "detect_anomalies": handle_detect_anomalies,
    "get_revenue_trends": handle_revenue_trends,
    "get_sales_velocity": handle_sales_velocity,
    "get_top_skus": handle_top_skus,
    "get_customer_concentration": handle_customer_concentration,
    "get_seasonality_analysis": handle_seasonality,
    # Supplier & Graph
    "get_supplier_risk_scores": handle_supplier_risk_scores,
    "get_supplier_performance": handle_supplier_performance,
    "get_supplier_concentration": handle_supplier_concentration,
    "get_supplier_network": handle_supplier_network,
    "find_single_source_risks": handle_single_source,
    "ripple_effect_analysis": handle_ripple,
    "get_lead_time_variability": handle_lead_time_var,
    "find_alternative_suppliers": handle_find_alternatives,
    # File & Data
    "list_uploads": handle_list_uploads,
    "get_schema_info": handle_schema_info,
    "run_sql_query": handle_run_sql,
    "get_version_history": handle_version_history,
    "trigger_database_refresh": handle_database_refresh,
    # New
    "get_shipment_tracking": handle_shipment_tracking,
    "get_product_catalog": handle_product_catalog,
}
