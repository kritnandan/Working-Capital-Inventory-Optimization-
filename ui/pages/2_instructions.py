import streamlit as st
import json

st.set_page_config(page_title="Setup & Instructions", page_icon="📖", layout="wide")

st.title("📖 AI Integration Setup")
st.markdown("Connect **Claude Desktop** or **Cursor IDE** to query your supply chain data in plain English.")

# ─── Prerequisites Banner ────────────────────────────────────────────────────
st.info("**Prerequisite:** Docker must be running and the WC Optimizer containers must be active (`docker compose up`).")

# ─── Step 1: MCP Configuration ───────────────────────────────────────────────
st.markdown("---")
st.markdown("## Step 1 — Copy Your MCP Configuration")
st.markdown(
    "Both **Claude Desktop** and **Cursor IDE** use the same configuration. "
    "It connects via `docker exec` — **no Node.js, no npm packages needed.**"
)

mcp_config = {
    "mcpServers": {
        "wc-optimizer": {
            "command": "docker",
            "args": [
                "exec",
                "-i",
                "wc-optimizer-mcp-sse-1",
                "python3",
                "/app/mcp_servers/stdio_server.py"
            ]
        }
    }
}
config_json = json.dumps(mcp_config, indent=2)

st.code(config_json, language="json")

col_dl1, col_dl2, col_spacer = st.columns([1, 1, 3])
with col_dl1:
    st.download_button(
        label="⬇️ claude_desktop_config.json",
        data=config_json,
        file_name="claude_desktop_config.json",
        mime="application/json",
        use_container_width=True,
    )
with col_dl2:
    st.download_button(
        label="⬇️ cursor_mcp.json",
        data=config_json,
        file_name="cursor_mcp.json",
        mime="application/json",
        use_container_width=True,
    )

# ─── Step 2: Client Setup ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Step 2 — Configure Your AI Client")

tab_claude, tab_cursor = st.tabs(["💬  Claude Desktop", "⌨️  Cursor IDE"])

with tab_claude:
    st.markdown("### Claude Desktop Setup")
    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        st.markdown("""
**Installation Steps:**

1. Download and install [Claude Desktop](https://claude.ai/download)
2. Open **Settings** (`Cmd + ,` on Mac / menu → Settings on Windows)
3. Click **Developer** in the left sidebar → **Edit Config**
4. **Replace the file contents** with the JSON from Step 1
5. Save the file
6. **Fully quit** Claude Desktop — use `Cmd+Q` on Mac or right-click the taskbar icon on Windows (don't just close the window)
7. Reopen Claude Desktop
        """)
    with col_b:
        st.markdown("""
**Config File Location:**
        """)
        st.code("macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json", language="text")
        st.code("Windows: %APPDATA%\\Claude\\claude_desktop_config.json", language="text")
        st.success("✅ **Success:** Look for the 🔌 plug icon in the chat input box — that means **42 tools are connected**.")
        st.warning("⚠️ Claude Desktop requires a full restart (Cmd+Q), not just closing the window.")

with tab_cursor:
    st.markdown("### Cursor IDE Setup")
    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        st.markdown("""
**Installation Steps:**

1. Download and install [Cursor](https://cursor.sh)
2. Open **Settings** → **Cursor Settings** → **Features** tab
3. Scroll to the **MCP** section
4. Click **Add New MCP Server**
5. Set **Type** to `stdio`, **Command** to `docker`
6. Set **Args** to:
```
exec -i wc-optimizer-mcp-sse-1 python3 /app/mcp_servers/stdio_server.py
```
7. Click **Save**
        """)
    with col_b:
        st.markdown("**Or paste the JSON from Step 1 directly into:**")
        st.code("~/.cursor/mcp.json", language="text")
        st.code(config_json, language="json")
        st.success("✅ **Success:** MCP tools appear in your AI chat panel.")

# ─── Step 3: Sample Questions ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Step 3 — Start Asking Questions")
st.markdown("Once connected, here are some questions you can ask:")

q_col1, q_col2, q_col3 = st.columns(3)

with q_col1:
    with st.container(border=True):
        st.markdown("**📦 Inventory**")
        st.markdown("""
- *Which SKUs need reordering?*
- *Find dead stock older than 90 days*
- *Show overstock tying up cash*
- *Calculate safety stock for SKU-001*
- *Predict stockouts for next 14 days*
- *Classify SKUs by ABC-XYZ*
        """)

with q_col2:
    with st.container(border=True):
        st.markdown("**💰 Cash & CCC**")
        st.markdown("""
- *What is my Cash Conversion Cycle?*
- *How much cash is trapped in inventory?*
- *If I cut DIO by 10 days, what's freed?*
- *Show AR aging analysis*
- *What's my DSO by customer?*
- *What's my DPO by supplier?*
        """)

with q_col3:
    with st.container(border=True):
        st.markdown("**🏭 Suppliers & Data**")
        st.markdown("""
- *Which suppliers have the highest risk?*
- *Find single-source products*
- *What if Supplier X fails?*
- *Find alternative suppliers for SKU-012*
- *Run SQL: SELECT * FROM ar_ledger LIMIT 10*
- *Show the product catalog (ABC class A)*
        """)

# ─── Available Tools ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🛠️ All 42 Available Tools", expanded=False):
    t1, t2, t3 = st.columns(3)

    with t1:
        st.markdown("**Dashboard & Overview**")
        st.code("get_full_dashboard\nget_kpi_summary\nget_data_quality_report", language="text")

        st.markdown("**Inventory (10)**")
        st.code("""get_reorder_alerts
get_smart_reorder_recommendations
calculate_safety_stock
calculate_eoq
get_inventory_turnover
get_inventory_aging
get_dead_stock
get_overstock_analysis
get_stockout_risk
get_abc_xyz_classification""", language="text")

    with t2:
        st.markdown("**Cash Cycle & WC (4)**")
        st.code("""simulate_ccc_improvement
get_working_capital_summary
get_carrying_cost_analysis
get_pareto_analysis""", language="text")

        st.markdown("**Demand & Sales (7)**")
        st.code("""forecast_demand
detect_anomalies
get_revenue_trends
get_sales_velocity
get_top_skus
get_customer_concentration
get_seasonality_analysis""", language="text")

    with t3:
        st.markdown("**Supplier Risk & Graph (8)**")
        st.code("""get_supplier_risk_scores
get_supplier_performance
get_supplier_concentration
get_supplier_network
find_single_source_risks
ripple_effect_analysis
get_lead_time_variability
find_alternative_suppliers""", language="text")

        st.markdown("**AR/AP & Cash Flow (5)**")
        st.code("""get_ar_aging
get_dso_analysis
get_dpo_analysis
get_shipment_tracking
get_product_catalog""", language="text")

        st.markdown("**Data & Admin (5)**")
        st.code("""list_uploads
get_schema_info
run_sql_query
get_version_history
trigger_database_refresh""", language="text")

# ─── Troubleshooting ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🐛 Troubleshooting", expanded=False):
    st.markdown("""
| Problem | Solution |
|---------|----------|
| Claude Desktop shows red error | Fully quit (Cmd+Q) and reopen. Don't just close the window. |
| Claude Desktop crashes on launch | Your JSON config has a syntax error — validate at [jsonlint.com](https://jsonlint.com) |
| "Container not found" error | Run `docker compose up` and wait for all 4 containers to start |
| Cursor not showing 42 tools | Remove and re-add the MCP server in Cursor settings |
| Tools return "No data uploaded yet" | Upload CSV files from the **Upload Data** page first |
| `run_sql_query` rejects write queries | Correct — this is a security feature. Only SELECT queries are allowed. |

**Useful commands:**
```bash
# Check container status
docker ps

# View MCP server logs
docker logs wc-optimizer-mcp-sse-1

# Restart all containers
docker compose restart

# Full reset (wipes all data)
docker compose down -v && docker compose up --build
```
    """)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("🔒 **Privacy:** All data stays on your local machine. MCP connects via `docker exec` — no data leaves your computer.")
