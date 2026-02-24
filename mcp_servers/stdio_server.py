"""
MCP Stdio Server for Claude Desktop
Runs inside Docker — zero Node.js dependency.
"""

import os, sys, json, asyncio
from typing import Any, Dict, List, Sequence
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

os.environ.setdefault("DUCKDB_PATH", "/data/supply_chain.duckdb")
os.environ.setdefault("FALKORDB_HOST", "falkordb")
os.environ.setdefault("FALKORDB_PORT", "6379")

sys.path.insert(0, "/app")

app = Server("wc-optimizer-mcp")

from mcp_servers.tool_handlers import TOOL_MAP

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(name="get_full_dashboard", description="Complete KPI dashboard: revenue, inventory turnover, supplier ratings, order volumes, CCC metrics", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_kpi_summary", description="Get working capital KPIs: CCC, DIO, DSO, DPO", inputSchema={"type":"object","properties":{"period":{"type":"string","enum":["7d","30d","90d"],"default":"30d"}}}),
        Tool(name="get_data_quality_report", description="Check data quality across all uploaded tables", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_reorder_alerts", description="List SKUs below reorder point", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_smart_reorder_recommendations", description="Priority-ranked reorder suggestions", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":20}}}),
        Tool(name="calculate_safety_stock", description="Calculate safety stock for SKUs", inputSchema={"type":"object","properties":{"skus":{"type":"array","items":{"type":"string"}},"service_level":{"type":"number","default":0.95}},"required":["skus"]}),
        Tool(name="calculate_eoq", description="Economic Order Quantity", inputSchema={"type":"object","properties":{"skus":{"type":"array","items":{"type":"string"}},"order_cost":{"type":"number","default":50},"holding_cost_pct":{"type":"number","default":0.25}},"required":["skus"]}),
        Tool(name="get_inventory_turnover", description="Inventory turnover ratio per SKU", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":50}}}),
        Tool(name="get_inventory_aging", description="Age analysis of inventory", inputSchema={"type":"object","properties":{"buckets":{"type":"string","default":"0-30,31-60,61-90,90+"}}}),
        Tool(name="get_dead_stock", description="Find inventory with no sales movement", inputSchema={"type":"object","properties":{"days":{"type":"integer","default":90}}}),
        Tool(name="get_overstock_analysis", description="Find items with excess inventory", inputSchema={"type":"object","properties":{"threshold_multiplier":{"type":"number","default":3.0}}}),
        Tool(name="get_stockout_risk", description="Predict which SKUs will stock out", inputSchema={"type":"object","properties":{"horizon_days":{"type":"integer","default":14}}}),
        Tool(name="get_abc_xyz_classification", description="Classify SKUs: ABC and XYZ", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":100}}}),
        Tool(name="simulate_ccc_improvement", description="What-if: cash freed by reducing DIO/DSO or increasing DPO", inputSchema={"type":"object","properties":{"dio_reduction":{"type":"integer","default":0},"dso_reduction":{"type":"integer","default":0},"dpo_increase":{"type":"integer","default":0},"annual_revenue":{"type":"number"}}}),
        Tool(name="get_working_capital_summary", description="Cash trapped in inventory by category", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_carrying_cost_analysis", description="Annual cost of holding inventory", inputSchema={"type":"object","properties":{"holding_cost_pct":{"type":"number","default":0.25}}}),
        Tool(name="get_pareto_analysis", description="80/20 analysis of SKUs", inputSchema={"type":"object","properties":{"dimension":{"type":"string","enum":["revenue","inventory_value","quantity"],"default":"revenue"}}}),
        Tool(name="forecast_demand", description="Moving-average demand forecast", inputSchema={"type":"object","properties":{"sku":{"type":"string"},"horizon_days":{"type":"integer","default":30},"window":{"type":"integer","default":7}},"required":["sku"]}),
        Tool(name="detect_anomalies", description="Statistical outlier detection", inputSchema={"type":"object","properties":{"table":{"type":"string","default":"sales"},"column":{"type":"string","default":"quantity"},"z_threshold":{"type":"number","default":2.0}}}),
        Tool(name="get_revenue_trends", description="Revenue over time with growth rates", inputSchema={"type":"object","properties":{"granularity":{"type":"string","enum":["daily","weekly","monthly"],"default":"monthly"}}}),
        Tool(name="get_sales_velocity", description="Units sold per day per SKU", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":30}}}),
        Tool(name="get_top_skus", description="Top SKUs by revenue", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":20}}}),
        Tool(name="get_customer_concentration", description="Revenue dependency on top customers", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":10}}}),
        Tool(name="get_seasonality_analysis", description="Detect seasonal patterns in sales", inputSchema={"type":"object","properties":{"sku":{"type":"string"}}}),
        Tool(name="get_supplier_risk_scores", description="Composite risk score per supplier", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_performance", description="Compare suppliers on delivery, lead time, rating", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_concentration", description="Dependency on each supplier by order volume", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_supplier_network", description="Full supplier-to-product mapping from graph", inputSchema={"type":"object","properties":{}}),
        Tool(name="find_single_source_risks", description="Products with only one supplier", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":50}}}),
        Tool(name="ripple_effect_analysis", description="Trace impact if a supplier fails", inputSchema={"type":"object","properties":{"supplier_id":{"type":"string"}},"required":["supplier_id"]}),
        Tool(name="get_lead_time_variability", description="Lead time stats per supplier", inputSchema={"type":"object","properties":{}}),
        Tool(name="find_alternative_suppliers", description="Find backup suppliers for a SKU", inputSchema={"type":"object","properties":{"sku":{"type":"string"}},"required":["sku"]}),
        Tool(name="list_uploads", description="Show status of all uploaded data files", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_schema_info", description="Column names, types, and sample data for a table", inputSchema={"type":"object","properties":{"table":{"type":"string"}},"required":["table"]}),
        Tool(name="run_sql_query", description="Run custom read-only SQL", inputSchema={"type":"object","properties":{"sql":{"type":"string"}},"required":["sql"]}),
        Tool(name="get_version_history", description="Show file upload history", inputSchema={"type":"object","properties":{}}),
        Tool(name="trigger_database_refresh", description="Check state of all databases", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_ar_aging", description="Accounts Receivable aging analysis", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_dso_analysis", description="Days Sales Outstanding analysis", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_dpo_analysis", description="Days Payable Outstanding analysis", inputSchema={"type":"object","properties":{}}),
        Tool(name="get_shipment_tracking", description="Track supplier shipments", inputSchema={"type":"object","properties":{"status":{"type":"string"}}}),
        Tool(name="get_product_catalog", description="Browse product catalog", inputSchema={"type":"object","properties":{"category":{"type":"string"},"abc_class":{"type":"string"}}}),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
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

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
