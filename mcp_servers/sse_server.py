"""
MCP SSE Server for WC Optimizer
Comprehensive working capital optimization tools — all query real data.
"""

import os, json, traceback, math
from typing import Any, Dict, List, Sequence
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
import duckdb
from falkordb import FalkorDB

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))

app = Server("wc-optimizer-mcp")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_duckdb():
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    return duckdb.connect(DUCKDB_PATH)

def get_graph():
    return FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT).select_graph("supply_chain")

def J(r): return json.dumps(r, indent=2, default=str)

def has(conn, t):
    try: return t in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]
    except: return False

def cnt(conn, t):
    try: return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except: return 0

def no_data(name): return [TextContent(type="text", text=J({"message": f"No {name} data uploaded yet."}))]


# ─── Tool Definitions ────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        # ── DASHBOARD & OVERVIEW ──
        Tool(name="get_full_dashboard", description="Complete KPI dashboard: revenue, inventory turnover, supplier ratings, order volumes, CCC metrics — all in one call", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_kpi_summary", description="Get working capital KPIs: CCC, DIO, DSO, DPO", inputSchema={"type":"object","properties":{"period":{"type":"string","enum":["7d","30d","90d"],"default":"30d"}}}),
        Tool(name="get_data_quality_report", description="Check data quality: nulls, duplicates, type mismatches across all uploaded tables", inputSchema={"type":"object","properties":{}}),

        # ── INVENTORY MANAGEMENT ──
        Tool(name="get_reorder_alerts", description="List SKUs below reorder point (critical/warning/out_of_stock)", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_smart_reorder_recommendations", description="Priority-ranked reorder suggestions with recommended quantities based on sales velocity and lead times", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":20}}}),
        Tool(name="calculate_safety_stock", description="Calculate safety stock: SS = Z × σ_demand × √(Lead Time)", inputSchema={"type":"object","properties":{"skus":{"type":"array","items":{"type":"string"}},"service_level":{"type":"number","default":0.95}},"required":["skus"]}),
        Tool(name="calculate_eoq", description="Economic Order Quantity: EOQ = √(2DS/H) where D=demand, S=order cost, H=holding cost", inputSchema={"type":"object","properties":{"skus":{"type":"array","items":{"type":"string"}},"order_cost":{"type":"number","default":50},"holding_cost_pct":{"type":"number","default":0.25}},"required":["skus"]}),
        Tool(name="get_inventory_turnover", description="Inventory turnover ratio per SKU (COGS / average inventory value)", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":50}}}),
        Tool(name="get_inventory_aging", description="Age analysis: how long inventory has been sitting unsold", inputSchema={"type":"object","properties":{"buckets":{"type":"string","default":"0-30,31-60,61-90,90+"}}}),
        Tool(name="get_dead_stock", description="Find inventory with no sales movement beyond N days", inputSchema={"type":"object","properties":{"days":{"type":"integer","default":90}}}),
        Tool(name="get_overstock_analysis", description="Find items with qty significantly above reorder point (excess inventory tying up cash)", inputSchema={"type":"object","properties":{"threshold_multiplier":{"type":"number","default":3.0}}}),
        Tool(name="get_stockout_risk", description="Predict which SKUs will stock out based on current velocity vs on-hand qty", inputSchema={"type":"object","properties":{"horizon_days":{"type":"integer","default":14}}}),
        Tool(name="get_abc_xyz_classification", description="Classify SKUs: ABC (revenue 80/15/5%) and XYZ (demand stability)", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":100}}}),

        # ── CASH CYCLE & WORKING CAPITAL ──
        Tool(name="simulate_ccc_improvement", description="What-if: how much cash freed by reducing DIO/DSO or increasing DPO", inputSchema={"type":"object","properties":{"dio_reduction":{"type":"integer","default":0},"dso_reduction":{"type":"integer","default":0},"dpo_increase":{"type":"integer","default":0},"annual_revenue":{"type":"number"}}}),
        Tool(name="get_working_capital_summary", description="How much cash is trapped in inventory, broken down by category", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_carrying_cost_analysis", description="Annual cost of holding inventory (storage, insurance, obsolescence)", inputSchema={"type":"object","properties":{"holding_cost_pct":{"type":"number","default":0.25,"description":"Annual holding cost as % of inventory value"}}}),
        Tool(name="get_pareto_analysis", description="80/20 analysis: which % of SKUs drive what % of revenue/inventory value", inputSchema={"type":"object","properties":{"dimension":{"type":"string","enum":["revenue","inventory_value","quantity"],"default":"revenue"}}}),

        # ── DEMAND & SALES ──
        Tool(name="forecast_demand", description="Moving-average demand forecast per SKU for next N days", inputSchema={"type":"object","properties":{"sku":{"type":"string"},"horizon_days":{"type":"integer","default":30},"window":{"type":"integer","default":7}},"required":["sku"]}),
        Tool(name="detect_anomalies", description="Statistical outlier detection (Z-score) across sales, inventory, or suppliers", inputSchema={"type":"object","properties":{"table":{"type":"string","enum":["sales","inventory","suppliers"],"default":"sales"},"column":{"type":"string","default":"quantity"},"z_threshold":{"type":"number","default":2.0}}}),
        Tool(name="get_revenue_trends", description="Revenue over time: daily/weekly/monthly aggregation with growth rates", inputSchema={"type":"object","properties":{"granularity":{"type":"string","enum":["daily","weekly","monthly"],"default":"monthly"}}}),
        Tool(name="get_sales_velocity", description="Units sold per day per SKU — shows fastest and slowest movers", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":30}}}),
        Tool(name="get_top_skus", description="Top SKUs by revenue", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":20}}}),
        Tool(name="get_customer_concentration", description="Revenue dependency on top customers — risk if any single customer leaves", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":10}}}),
        Tool(name="get_seasonality_analysis", description="Detect seasonal patterns in sales by month/quarter", inputSchema={"type":"object","properties":{"sku":{"type":"string","description":"Optional: specific SKU (omit for all)"}}}),

        # ── SUPPLIER & GRAPH ──
        Tool(name="get_supplier_risk_scores", description="Composite risk score per supplier: lead time + rating + single-source + volume dependency", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_performance", description="Compare suppliers on delivery, lead time, product count, and rating", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_concentration", description="How dependent are you on each supplier by order volume", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_network", description="Full supplier-to-product mapping from graph", inputSchema={"type":"object","properties":{}}),
        Tool(name="find_single_source_risks", description="Products with only one supplier", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":50}}}),
        Tool(name="ripple_effect_analysis", description="Trace impact if a supplier fails", inputSchema={"type":"object","properties":{"supplier_id":{"type":"string"}},"required":["supplier_id"]}),
        Tool(name="get_lead_time_variability", description="Lead time stats per supplier", inputSchema={"type":"object","properties":{}}),
        Tool(name="find_alternative_suppliers", description="Find backup suppliers for a SKU", inputSchema={"type":"object","properties":{"sku":{"type":"string"}},"required":["sku"]}),

        # ── FILE & DATA ──
        Tool(name="list_uploads", description="Show status of all uploaded data files", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_schema_info", description="Column names, types, and sample data for a table", inputSchema={"type":"object","properties":{"table":{"type":"string"}},"required":["table"]}),
        Tool(name="run_sql_query", description="Run custom read-only SQL. Tables: products, customers, suppliers, inventory_snapshot, sales_transactions, purchase_orders, ar_ledger, ap_ledger, shipments", inputSchema={"type":"object","properties":{"sql":{"type":"string"}},"required":["sql"]}),
        Tool(name="get_version_history", description="Show file upload history with timestamps, filenames, and row counts", inputSchema={"type":"object","properties":{}}),
        Tool(name="trigger_database_refresh", description="Check and report current state of all databases (DuckDB tables + FalkorDB graph)", inputSchema={"type":"object","properties":{}}),

        # ── NEW: CCC & AR/AP ──
        Tool(name="get_ar_aging", description="Accounts Receivable aging analysis — outstanding amounts by bucket, disputes, write-offs", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_dso_analysis", description="Days Sales Outstanding analysis — overall DSO and breakdown by customer", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_dpo_analysis", description="Days Payable Outstanding analysis — overall DPO and breakdown by supplier", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_shipment_tracking", description="Track supplier shipments — in-transit, delivered, delayed", inputSchema={"type":"object","properties":{"status":{"type":"string","description":"Filter by status: In Transit, Delivered, Delayed"}}}),
        Tool(name="get_product_catalog", description="Browse product catalog with optional category/ABC class filters", inputSchema={"type":"object","properties":{"category":{"type":"string"},"abc_class":{"type":"string"}}}),
    ]


# ─── Tool dispatch ────────────────────────────────────────────────────────────

from mcp_servers.tool_handlers import TOOL_MAP

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Route tool calls to handlers"""
    try:
        handler = TOOL_MAP.get(name)
        if not handler:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        result = handler(arguments or {})
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        import traceback
        return [TextContent(type="text", text=json.dumps({
            "error": str(e), "traceback": traceback.format_exc()
        }))]


# ─── SSE Transport ────────────────────────────────────────────────────────────

sse = SseServerTransport("/messages")

# The MCP SSE handlers need raw ASGI (scope, receive, send).
# Starlette Route wraps handlers, so we build a raw ASGI app
# that delegates Starlette routing but captures send.

async def sse_app(scope, receive, send):
    """Raw ASGI app that handles /sse and /messages routes"""
    path = scope.get("path", "")

    if path == "/sse":
        async with sse.connect_sse(scope, receive, send) as (rs, ws):
            await app.run(rs, ws, app.create_initialization_options())
    elif path.startswith("/messages"):
        await sse.handle_post_message(scope, receive, send)
    else:
        # 404 for unknown paths
        from starlette.responses import Response
        resp = Response("Not Found", status_code=404)
        await resp(scope, receive, send)

if __name__ == "__main__":
    print("Starting MCP SSE Server on port 3001...")
    print(f"Tools available: {len(TOOL_MAP)}")
    uvicorn.run(sse_app, host="0.0.0.0", port=3001)
