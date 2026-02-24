from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import duckdb

router = APIRouter()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")


def get_duckdb():
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    return duckdb.connect(DUCKDB_PATH)


def table_exists(conn, name):
    try:
        return name in [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    except Exception:
        return False


@router.get("/kpi/summary")
async def get_kpi_summary():
    """Get key KPIs: CCC, DIO, DSO, DPO — computed from real data"""
    conn = get_duckdb()
    result = {"period": "all_time", "unit": "days", "formula": "CCC = DIO + DSO - DPO"}

    if not table_exists(conn, "sales") and not table_exists(conn, "inventory"):
        conn.close()
        return {"message": "No data uploaded yet. Upload sales and inventory data to see KPIs."}

    # DIO
    try:
        if table_exists(conn, "inventory") and table_exists(conn, "sales"):
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(i.qty_on_hand * i.unit_cost), 0),
                    COALESCE((SELECT SUM(revenue) / NULLIF(COUNT(DISTINCT date), 0) FROM sales), 1)
                FROM inventory i
            """).fetchone()
            result["dio"] = round(row[0] / row[1], 1) if row[1] > 0 else 0
        else:
            result["dio"] = 0
    except Exception:
        result["dio"] = 0

    # DSO — simplified (total revenue / daily revenue * assumed 30-day cycle)
    try:
        if table_exists(conn, "sales"):
            row = conn.execute("SELECT SUM(revenue), COUNT(DISTINCT date) FROM sales").fetchone()
            total, days = row[0] or 0, row[1] or 1
            result["dso"] = round(30.0, 1)  # simplified — full DSO needs AR data
            result["dso_note"] = "Simplified — full DSO needs accounts receivable data"
        else:
            result["dso"] = 0
    except Exception:
        result["dso"] = 0

    result["dpo"] = 0
    result["dpo_note"] = "DPO needs accounts payable data"
    result["ccc"] = round(result.get("dio", 0) + result.get("dso", 0) - result.get("dpo", 0), 1)

    conn.close()
    return result


@router.get("/abc-xyz")
async def get_abc_xyz_classification():
    """Get ABC-XYZ classification of SKUs from real sales data"""
    conn = get_duckdb()
    if not table_exists(conn, "sales"):
        conn.close()
        return {"message": "No sales data uploaded yet."}

    try:
        df = conn.execute("""
            WITH sku_stats AS (
                SELECT sku, SUM(revenue) as total_revenue, STDDEV(quantity) as qty_std, AVG(quantity) as qty_avg
                FROM sales GROUP BY sku
            ),
            ranked AS (
                SELECT *, total_revenue / SUM(total_revenue) OVER () * 100 as revenue_pct,
                    SUM(total_revenue) OVER (ORDER BY total_revenue DESC) / SUM(total_revenue) OVER () * 100 as cum_pct,
                    CASE WHEN qty_avg > 0 THEN qty_std / qty_avg ELSE 0 END as cv
                FROM sku_stats
            )
            SELECT sku, ROUND(total_revenue, 2) as revenue, ROUND(revenue_pct, 2) as revenue_pct,
                CASE WHEN cum_pct <= 80 THEN 'A' WHEN cum_pct <= 95 THEN 'B' ELSE 'C' END as abc_class,
                CASE WHEN cv < 0.5 THEN 'X' WHEN cv < 1.0 THEN 'Y' ELSE 'Z' END as xyz_class
            FROM ranked ORDER BY total_revenue DESC LIMIT 100
        """).fetchdf()
        conn.close()
        return {"classification": df.to_dict("records"), "total": len(df)}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reorder-alerts")
async def get_reorder_alerts():
    """Get SKUs below reorder point from real inventory data"""
    conn = get_duckdb()
    if not table_exists(conn, "inventory"):
        conn.close()
        return {"message": "No inventory data uploaded yet."}

    try:
        df = conn.execute("""
            SELECT sku, qty_on_hand, reorder_point,
                CASE WHEN qty_on_hand < reorder_point THEN 'critical'
                     WHEN qty_on_hand < reorder_point * 1.2 THEN 'warning' ELSE 'ok' END as status
            FROM inventory
            WHERE qty_on_hand < reorder_point * 1.2
            ORDER BY CAST(qty_on_hand AS FLOAT) / NULLIF(reorder_point, 0) ASC
        """).fetchdf()
        conn.close()
        return {
            "alerts": df.to_dict("records"),
            "total_alerts": len(df),
            "critical_count": len(df[df["status"] == "critical"]) if len(df) > 0 else 0,
            "warning_count": len(df[df["status"] == "warning"]) if len(df) > 0 else 0
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dead-stock")
async def get_dead_stock(days: int = 90):
    """Find inventory with no movement beyond N days — from real data"""
    conn = get_duckdb()
    if not table_exists(conn, "inventory"):
        conn.close()
        return {"message": "No inventory data uploaded yet."}

    try:
        df = conn.execute(f"""
            SELECT i.sku, i.qty_on_hand, i.unit_cost,
                COALESCE(i.qty_on_hand * i.unit_cost, 0) as value_at_risk,
                MAX(s.date) as last_sale_date
            FROM inventory i LEFT JOIN sales s ON i.sku = s.sku
            GROUP BY i.sku, i.qty_on_hand, i.unit_cost
            HAVING MAX(s.date) IS NULL OR CURRENT_DATE - MAX(s.date) > {days}
            ORDER BY value_at_risk DESC
        """).fetchdf()
        conn.close()
        total_value = float(df["value_at_risk"].sum()) if len(df) > 0 else 0
        return {
            "days_threshold": days,
            "dead_stock": df.to_dict("records"),
            "total_items": len(df),
            "total_value_at_risk": round(total_value, 2)
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-skus")
async def get_top_skus(limit: int = 20):
    """Get top SKUs by revenue from real sales data"""
    conn = get_duckdb()
    if not table_exists(conn, "sales"):
        conn.close()
        return {"message": "No sales data uploaded yet."}

    try:
        df = conn.execute(f"""
            SELECT sku, SUM(revenue) as revenue, SUM(quantity) as units_sold
            FROM sales GROUP BY sku ORDER BY revenue DESC LIMIT {limit}
        """).fetchdf()
        conn.close()
        return {"skus": df.to_dict("records"), "limit": limit}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
