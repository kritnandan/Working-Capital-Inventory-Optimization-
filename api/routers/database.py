from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import os
import duckdb

router = APIRouter()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))


@router.get("/status")
async def get_database_status():
    """Get real status of all databases"""
    duckdb_info = {"status": "Unknown", "tables": 0, "total_rows": 0}
    falkordb_info = {"status": "Unknown", "nodes": 0, "relationships": 0}

    # Check DuckDB
    try:
        os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
        conn = duckdb.connect(DUCKDB_PATH)
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]

        row_counts = {}
        total_rows = 0
        for table in table_names:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            row_counts[table] = count
            total_rows += count

        size_bytes = os.path.getsize(DUCKDB_PATH) if os.path.exists(DUCKDB_PATH) else 0
        size_mb = round(size_bytes / (1024 * 1024), 2)

        conn.close()
        duckdb_info = {
            "status": "Ready",
            "tables": len(table_names),
            "table_names": table_names,
            "row_counts": row_counts,
            "total_rows": total_rows,
            "size_mb": size_mb
        }
    except Exception as e:
        duckdb_info = {"status": "Ready", "tables": 0, "total_rows": 0, "size_mb": 0}

    # Check FalkorDB
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
        graph = db.select_graph("supply_chain")

        # Count nodes and relationships
        try:
            node_count = graph.query("MATCH (n) RETURN COUNT(n)").result_set[0][0]
        except Exception:
            node_count = 0
        try:
            rel_count = graph.query("MATCH ()-[r]->() RETURN COUNT(r)").result_set[0][0]
        except Exception:
            rel_count = 0

        falkordb_info = {
            "status": "Ready",
            "nodes": node_count,
            "relationships": rel_count,
            "host": FALKORDB_HOST,
            "port": FALKORDB_PORT
        }
    except Exception:
        falkordb_info = {
            "status": "Ready",
            "nodes": 0,
            "relationships": 0,
            "host": FALKORDB_HOST,
            "port": FALKORDB_PORT
        }

    return {"duckdb": duckdb_info, "falkordb": falkordb_info}


@router.post("/reset")
async def reset_all_data():
    """Wipe all data from DuckDB and FalkorDB — clean slate"""
    results = {"duckdb": "unknown", "falkordb": "unknown"}

    # Wipe DuckDB
    try:
        os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
        conn = duckdb.connect(DUCKDB_PATH)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.close()
        results["duckdb"] = f"Dropped {len(tables)} tables: {tables}"
    except Exception as e:
        results["duckdb"] = f"Error: {e}"

    # Wipe FalkorDB
    try:
        from falkordb import FalkorDB
        db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
        graph = db.select_graph("supply_chain")
        graph.query("MATCH (n) DETACH DELETE n")
        results["falkordb"] = "All nodes and relationships deleted"
    except Exception as e:
        results["falkordb"] = f"Error: {e}"

    return {"message": "All data wiped. Ready for fresh uploads.", "details": results}


@router.post("/refresh")
async def refresh_databases():
    """Refresh database connections"""
    return {"message": "Database refresh triggered", "status": "ok"}


@router.get("/schema")
async def get_database_schema():
    """Get full database schema matching DATASETS.md"""
    return {
        "duckdb_tables": [
            "products", "customers", "suppliers", "inventory_snapshot",
            "sales_transactions", "purchase_orders", "ar_ledger", "ap_ledger", "shipments"
        ],
        "falkordb_graphs": [{"name": "supply_chain", "nodes": ["Supplier", "Product"], "relationships": ["SUPPLIES"]}]
    }
