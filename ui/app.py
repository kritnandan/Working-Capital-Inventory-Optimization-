import streamlit as st

st.set_page_config(
    page_title="WC Optimizer",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💰 WC Optimizer")
st.subheader("Working Capital & Inventory Optimization Platform")

st.markdown("""
Welcome to **WC Optimizer** — an open-source, AI-powered platform for optimizing working capital through inventory, receivables, and payables analysis.

### Quick Start

1. **📤 Upload Data** — Use the Upload page to add your CSV/Excel files.
2. **📊 View Analytics** — Instantly see where your data is stored (DuckDB/FalkorDB).
3. **🤖 Connect AI** — Go to the Instructions page for step-by-step setup to connect Claude Desktop or Cursor IDE using the latest MCP configuration (secure, local, and private via Docker).
4. **💬 Ask Questions** — Use natural language to analyze your supply chain and working capital.

### Data Flow

```
Your Files → Streamlit UI → FastAPI → DuckDB (Analytics) + FalkorDB (Graph)
                    ↓
                MCP Server (Docker) → Claude/Cursor → Insights
```

### Supported Datasets (9 files)

| # | Dataset | Key Columns | Destination |
|---|---------|-------------|-------------|
| 1 | **Products** | product_id, product_name, unit_cost, unit_price | DuckDB |
| 2 | **Customers** | customer_id, customer_name, segment, credit_limit | DuckDB |
| 3 | **Suppliers** | supplier_id, supplier_name, avg_lead_time_days | DuckDB + FalkorDB |
| 4 | **Inventory Snapshot** | product_id, qty_on_hand, inventory_value | DuckDB |
| 5 | **Sales Transactions** | product_id, customer_id, total_revenue | DuckDB |
| 6 | **Purchase Orders** | po_id, supplier_id, product_id, qty_ordered | DuckDB + FalkorDB |
| 7 | **AR Ledger** | invoice_id, customer_id, days_to_pay, aging_bucket | DuckDB |
| 8 | **AP Ledger** | invoice_id, supplier_id, actual_days_to_pay | DuckDB |
| 9 | **Shipments** | shipment_id, supplier_id, status, delay_days | DuckDB |

### CCC Engine

```
DIO (inventory_snapshot) + DSO (ar_ledger) − DPO (ap_ledger) = CCC
```

### Navigation

Use the sidebar to:
- **Upload Data** — Upload and manage your 9 dataset files
- **Instructions** — Step-by-step guide to connect Claude Desktop or Cursor IDE via MCP (over 37 tools supported)

---

**Status:** ✅ Docker Ready
""")

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.info("Select a page above ↑")
