"""
Database initialization script for WC Optimizer
Creates DuckDB schema and FalkorDB graph structure
"""

import os
import duckdb
from falkordb import FalkorDB

def init_duckdb():
    """Initialize DuckDB tables"""
    db_path = os.getenv("DUCKDB_PATH", "./data/supply_chain.duckdb")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = duckdb.connect(db_path)
    
    # Core data tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            date DATE,
            sku VARCHAR,
            quantity INTEGER,
            revenue DECIMAL(12,2),
            customer_name VARCHAR,
            region VARCHAR,
            category VARCHAR
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sku VARCHAR,
            qty_on_hand INTEGER,
            reorder_point INTEGER,
            location VARCHAR,
            unit_cost DECIMAL(10,2),
            supplier_id VARCHAR,
            last_updated DATE
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id VARCHAR,
            supplier_name VARCHAR,
            lead_time INTEGER,
            contact_email VARCHAR,
            rating DECIMAL(3,1),
            country VARCHAR
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            po_number VARCHAR,
            sku VARCHAR,
            quantity INTEGER,
            order_date DATE,
            delivery_date DATE,
            supplier_id VARCHAR,
            status VARCHAR
        )
    """)
    
    # File metadata tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_uploads (
            id INTEGER PRIMARY KEY,
            file_category VARCHAR(50),
            filename VARCHAR(255),
            upload_timestamp TIMESTAMP,
            uploaded_by VARCHAR(100),
            row_count INTEGER,
            file_size_bytes BIGINT,
            status VARCHAR(20),
            quality_score DECIMAL(5,2),
            validation_errors JSON,
            storage_path VARCHAR(500)
        )
    """)
    
    # KPI tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kpi_daily (
            date DATE,
            dio DECIMAL(8,2),
            dso DECIMAL(8,2),
            dpo DECIMAL(8,2),
            ccc DECIMAL(8,2),
            inventory_turnover DECIMAL(8,2)
        )
    """)
    
    conn.close()
    print(f"✅ DuckDB initialized at {db_path}")

def init_falkordb():
    """Initialize FalkorDB graph"""
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    
    try:
        db = FalkorDB(host=host, port=port)
        graph = db.select_graph("supply_chain")
        
        # Create indices and constraints
        # Note: FalkorDB uses Cypher queries
        
        # Create sample graph schema
        graph.query("""
            CREATE INDEX ON :Supplier(supplier_id)
        """)
        
        graph.query("""
            CREATE INDEX ON :Product(sku)
        """)
        
        print(f"✅ FalkorDB initialized at {host}:{port}")
        print("✅ Graph 'supply_chain' ready")
        
    except Exception as e:
        print(f"⚠️ FalkorDB connection failed: {e}")
        print("   Graph will be initialized when FalkorDB is available")

def main():
    print("🚀 Initializing WC Optimizer databases...")
    print("-" * 50)
    
    init_duckdb()
    init_falkordb()
    
    print("-" * 50)
    print("✅ Database initialization complete!")

if __name__ == "__main__":
    main()
