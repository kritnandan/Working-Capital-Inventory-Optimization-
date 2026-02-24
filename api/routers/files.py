from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
from datetime import datetime
import duckdb

router = APIRouter()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))

# All 9 DATASETS.md categories
VALID_CATEGORIES = [
    "products", "customers", "suppliers", "inventory_snapshot",
    "sales_transactions", "purchase_orders", "ar_ledger", "ap_ledger", "shipments"
]

# Categories that get synced to FalkorDB graph
GRAPH_CATEGORIES = ["suppliers", "purchase_orders"]


class UploadResponse(BaseModel):
    file_category: str
    filename: str
    row_count: int
    column_count: int
    status: str
    destination: str
    message: str


def get_duckdb():
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    return duckdb.connect(DUCKDB_PATH)


def sync_suppliers_to_graph(df: pd.DataFrame):
    """Create Supplier nodes in FalkorDB"""
    try:
        from falkordb import FalkorDB
        graph = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT).select_graph("supply_chain")
        try: graph.query("CREATE INDEX ON :Supplier(supplier_id)")
        except: pass

        for _, row in df.iterrows():
            sid = str(row.get("supplier_id", ""))
            name = str(row.get("supplier_name", "")).replace("'", "\\'")
            lt = float(row.get("avg_lead_time_days", 0)) if pd.notna(row.get("avg_lead_time_days")) else 0
            rating = float(row.get("risk_score", 0)) if pd.notna(row.get("risk_score")) else 0
            otd = float(row.get("on_time_delivery_rate", 0)) if pd.notna(row.get("on_time_delivery_rate")) else 0
            country = str(row.get("country", "")).replace("'", "\\'") if pd.notna(row.get("country")) else ""
            graph.query(f"""
                MERGE (s:Supplier {{supplier_id: '{sid}'}})
                SET s.supplier_name = '{name}', s.lead_time = {lt},
                    s.rating = {rating}, s.otd_rate = {otd}, s.country = '{country}'
            """)
        return True
    except Exception as e:
        print(f"FalkorDB supplier sync: {e}")
        return False


def sync_po_to_graph(df: pd.DataFrame):
    """Create Product nodes and SUPPLIES relationships"""
    try:
        from falkordb import FalkorDB
        graph = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT).select_graph("supply_chain")
        try: graph.query("CREATE INDEX ON :Product(product_id)")
        except: pass
        try: graph.query("CREATE INDEX ON :Supplier(supplier_id)")
        except: pass

        for _, row in df.iterrows():
            pid = str(row.get("product_id", ""))
            sid = str(row.get("supplier_id", ""))
            if not pid or not sid: continue
            graph.query(f"MERGE (p:Product {{product_id: '{pid}'}})")
            graph.query(f"MERGE (s:Supplier {{supplier_id: '{sid}'}})")
            graph.query(f"""
                MATCH (s:Supplier {{supplier_id: '{sid}'}})
                MATCH (p:Product {{product_id: '{pid}'}})
                MERGE (s)-[:SUPPLIES]->(p)
            """)
        return True
    except Exception as e:
        print(f"FalkorDB PO sync: {e}")
        return False


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), category: str = "sales_transactions"):
    """Upload a file for any of the 9 DATASETS.md categories"""
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {VALID_CATEGORIES}")

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        elif file.filename.endswith('.xlsx'):
            df = pd.read_excel(file.file)
        else:
            raise HTTPException(status_code=400, detail="File must be CSV or XLSX")

        destination = "DuckDB + FalkorDB" if category in GRAPH_CATEGORIES else "DuckDB"

        # Save to DuckDB
        db_saved = False
        try:
            conn = get_duckdb()
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            if category in tables:
                conn.execute(f"DROP TABLE {category}")
            conn.execute(f"CREATE TABLE {category} AS SELECT * FROM df")

            # Track upload
            try:
                if "file_uploads" not in [t[0] for t in conn.execute("SHOW TABLES").fetchall()]:
                    conn.execute("""CREATE TABLE file_uploads (
                        id INTEGER, file_category VARCHAR, filename VARCHAR,
                        upload_timestamp TIMESTAMP, row_count INTEGER, status VARCHAR)""")
                conn.execute(f"""INSERT INTO file_uploads VALUES (
                    (SELECT COALESCE(MAX(id),0)+1 FROM file_uploads),
                    '{category}', '{file.filename}', CURRENT_TIMESTAMP, {len(df)}, 'uploaded')""")
            except Exception as e:
                print(f"Upload tracking: {e}")
            conn.close()
            db_saved = True
        except Exception as e:
            print(f"DuckDB save error: {e}")

        # Graph sync
        graph_synced = False
        if category == "suppliers":
            graph_synced = sync_suppliers_to_graph(df)
        elif category == "purchase_orders":
            graph_synced = sync_po_to_graph(df)

        msg = []
        if db_saved: msg.append(f"Saved {len(df):,} rows to DuckDB")
        if graph_synced: msg.append("synced to FalkorDB graph")

        return UploadResponse(
            file_category=category, filename=file.filename,
            row_count=len(df), column_count=len(df.columns),
            status="uploaded", destination=destination,
            message=" and ".join(msg) if msg else "Upload processed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_upload_status():
    """Get status of all 9 file uploads"""
    try:
        conn = get_duckdb()
        categories = {}
        for cat in VALID_CATEGORIES:
            try:
                tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
                if cat in tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM {cat}").fetchone()[0]
                    dest = "DuckDB + FalkorDB" if cat in GRAPH_CATEGORIES else "DuckDB"
                    categories[cat] = {"status": "uploaded", "row_count": count, "destination": dest}
                else:
                    categories[cat] = {"status": "not_uploaded"}
            except:
                categories[cat] = {"status": "not_uploaded"}
        conn.close()
        return {"categories": categories}
    except:
        return {"categories": {c: {"status": "unknown"} for c in VALID_CATEGORIES}}
