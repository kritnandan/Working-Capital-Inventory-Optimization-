# MCP Setup Guide

Connect Claude Desktop or Cursor IDE to your supply chain data via MCP.

## Quick Setup

### 1. Start Services
```bash
docker compose up
```

### 2. MCP Configuration JSON
```json
{
  "mcpServers": {
    "wc-optimizer": {
      "url": "http://localhost:3001/sse"
    }
  }
}
```

### 3. Claude Desktop
- Settings → Developer → Edit Config → Paste JSON → Save → Restart Claude

### 4. Cursor IDE
- Settings → Features → MCP → Add New → Name: `wc-optimizer`, Type: `sse`, URL: `http://localhost:3001/sse`

---

## Available Tools (35 total)

### 📈 Dashboard & Overview (3)
| Tool | Description |
|------|-------------|
| `get_full_dashboard` | Complete KPI dashboard: revenue, turnover, supplier ratings, orders |
| `get_kpi_summary` | CCC, DIO, DSO, DPO working capital metrics |
| `get_data_quality_report` | Check nulls, duplicates, quality scores |

### 📦 Inventory Management (10)
| Tool | Description |
|------|-------------|
| `get_reorder_alerts` | SKUs below reorder point |
| `get_smart_reorder_recommendations` | Priority-ranked reorder suggestions with quantities |
| `calculate_safety_stock` | Safety stock = Z × σ × √(Lead Time) |
| `calculate_eoq` | Economic Order Quantity = √(2DS/H) |
| `get_inventory_turnover` | Turnover ratio per SKU |
| `get_inventory_aging` | Age buckets: 0-30d, 31-60d, 61-90d, 90+d |
| `get_dead_stock` | Items with no movement beyond N days |
| `get_overstock_analysis` | Excess inventory tying up cash |
| `get_stockout_risk` | Predict stockouts based on velocity |
| `get_abc_xyz_classification` | Revenue + demand stability classification |

### 💰 Cash Cycle & Working Capital (4)
| Tool | Description |
|------|-------------|
| `simulate_ccc_improvement` | What-if: cash freed by CCC improvements |
| `get_working_capital_summary` | Cash trapped in inventory by segment |
| `get_carrying_cost_analysis` | Annual cost of holding inventory |
| `get_pareto_analysis` | 80/20 analysis across revenue/inventory |

### 📉 Demand & Sales (7)
| Tool | Description |
|------|-------------|
| `forecast_demand` | Moving-average demand prediction per SKU |
| `detect_anomalies` | Z-score statistical outlier detection |
| `get_revenue_trends` | Daily/weekly/monthly revenue with growth rates |
| `get_sales_velocity` | Units sold per day (fastest/slowest movers) |
| `get_top_skus` | Top SKUs by revenue |
| `get_customer_concentration` | Revenue dependency on top customers |
| `get_seasonality_analysis` | Monthly seasonal patterns |

### ⚠️ Supplier & Graph (8)
| Tool | Description |
|------|-------------|
| `get_supplier_risk_scores` | Composite risk = lead time + rating + concentration |
| `get_supplier_performance` | Compare suppliers on multiple metrics |
| `get_supplier_concentration` | Volume dependency per supplier |
| `get_supplier_network` | Full supplier-product mapping (graph) |
| `find_single_source_risks` | Products with only one supplier |
| `ripple_effect_analysis` | Supplier failure impact |
| `get_lead_time_variability` | Lead time stats per supplier |
| `find_alternative_suppliers` | Backup suppliers for a SKU |

### 🗂️ File & Data (3)
| Tool | Description |
|------|-------------|
| `list_uploads` | Uploaded files status and destinations |
| `get_schema_info` | Table columns and sample data |
| `run_sql_query` | Custom read-only SQL queries |

---

## Adding New Tools

1. Add handler function in `mcp_servers/tool_handlers.py`
2. Add `TOOL_MAP` entry at the bottom of the file
3. Add `Tool()` definition in `mcp_servers/sse_server.py` → `list_tools()`
4. Restart: `docker compose restart mcp-sse`
