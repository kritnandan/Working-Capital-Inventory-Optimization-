import streamlit as st
import pandas as pd
import requests
import os

st.set_page_config(page_title="Upload Data", page_icon="📤")

st.title("📤 Data Upload")
st.subheader("Upload your 9 supply chain dataset files")

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── All 9 dataset slots matching DATASETS.md ─────────────────────────────────
FILE_SLOTS = {
    "products": {
        "icon": "🏷️", "name": "Products",
        "required_cols": ["product_id", "product_name", "unit_cost", "unit_price"],
        "optional_cols": ["category", "subcategory", "supplier_id", "lead_time_days", "abc_class", "xyz_class", "reorder_point", "economic_order_qty", "safety_stock_target"],
        "destination": "DuckDB",
        "description": "Master product catalog (200 SKUs)"
    },
    "customers": {
        "icon": "👥", "name": "Customers",
        "required_cols": ["customer_id", "customer_name"],
        "optional_cols": ["segment", "region", "state", "credit_limit", "contracted_payment_days", "risk_score", "ytd_revenue", "avg_days_to_pay"],
        "destination": "DuckDB",
        "description": "Customer master with credit profiles"
    },
    "suppliers": {
        "icon": "🏭", "name": "Suppliers",
        "required_cols": ["supplier_id", "supplier_name"],
        "optional_cols": ["category", "segment", "country", "contracted_payment_days", "avg_lead_time_days", "on_time_delivery_rate", "quality_rejection_rate", "risk_score", "annual_spend"],
        "destination": "DuckDB + FalkorDB",
        "description": "Supplier master with performance metrics"
    },
    "inventory_snapshot": {
        "icon": "📦", "name": "Inventory Snapshot",
        "required_cols": ["product_id", "qty_on_hand"],
        "optional_cols": ["snapshot_date", "location_id", "qty_in_transit", "qty_committed", "qty_available", "safety_stock_target", "reorder_point", "days_of_supply", "unit_cost", "inventory_value", "stock_status", "days_since_last_movement"],
        "destination": "DuckDB",
        "description": "Daily inventory positions per SKU per location"
    },
    "sales_transactions": {
        "icon": "💰", "name": "Sales Transactions",
        "required_cols": ["transaction_date", "product_id", "qty_sold", "total_revenue"],
        "optional_cols": ["transaction_id", "customer_id", "location_id", "unit_price", "unit_cost", "total_cost", "gross_profit", "profit_margin", "channel", "is_promotional", "invoice_id"],
        "destination": "DuckDB",
        "description": "Individual sales (~50K transactions)"
    },
    "purchase_orders": {
        "icon": "📝", "name": "Purchase Orders",
        "required_cols": ["po_id", "supplier_id", "product_id", "qty_ordered"],
        "optional_cols": ["po_date", "location_id", "qty_received", "unit_cost", "total_po_value", "expected_delivery_date", "actual_delivery_date", "po_status", "delay_days", "invoice_id"],
        "destination": "DuckDB + FalkorDB",
        "description": "Replenishment POs to suppliers (~2K)"
    },
    "ar_ledger": {
        "icon": "📨", "name": "AR Ledger",
        "required_cols": ["invoice_id", "customer_id", "invoice_amount"],
        "optional_cols": ["transaction_id", "invoice_date", "due_date", "paid_amount", "paid_date", "days_to_pay", "is_overdue", "days_overdue", "aging_bucket", "dispute_flag", "write_off_flag"],
        "destination": "DuckDB",
        "description": "Accounts Receivable — for DSO calculation"
    },
    "ap_ledger": {
        "icon": "📤", "name": "AP Ledger",
        "required_cols": ["invoice_id", "supplier_id", "invoice_amount"],
        "optional_cols": ["po_id", "invoice_date", "due_date", "paid_amount", "paid_date", "contracted_days", "actual_days_to_pay", "early_payment_discount", "payment_status", "dpo_contribution"],
        "destination": "DuckDB",
        "description": "Accounts Payable — for DPO calculation"
    },
    "shipments": {
        "icon": "🚚", "name": "Shipments",
        "required_cols": ["shipment_id", "po_id", "supplier_id"],
        "optional_cols": ["product_id", "origin_location", "destination_location_id", "ship_date", "expected_arrival_date", "actual_arrival_date", "qty_shipped", "freight_cost", "carrier", "tracking_number", "status", "delay_days"],
        "destination": "DuckDB",
        "description": "In-transit tracking for supplier shipments"
    }
}

# Session state
for k in FILE_SLOTS:
    if f"uploaded_{k}" not in st.session_state:
        st.session_state[f"uploaded_{k}"] = False

st.markdown("---")

# ── CCC Engine reminder ──────────────────────────────────────────────────────
st.info("💡 **CCC Engine:** Upload inventory_snapshot + ar_ledger + ap_ledger to enable full Cash Conversion Cycle analysis")

# ── Upload cards ──────────────────────────────────────────────────────────────
cols = st.columns(3)

for idx, (slot_key, info) in enumerate(FILE_SLOTS.items()):
    with cols[idx % 3]:
        with st.container(border=True):
            st.subheader(f"{info['icon']} {info['name']}")
            st.caption(info['description'])

            if st.session_state[f"uploaded_{slot_key}"]:
                st.success("✅ Uploaded")
            else:
                st.info("📭 Waiting")

            uploaded_file = st.file_uploader(
                f"Upload {info['name']}", type=['csv', 'xlsx'],
                key=f"upload_{slot_key}", label_visibility="collapsed"
            )

            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.success(f"✅ {len(df):,} rows × {len(df.columns)} cols")

                    missing = set(info['required_cols']) - set(df.columns)
                    if missing:
                        st.error(f"❌ Missing: {', '.join(missing)}")
                    else:
                        st.success("✅ Schema valid")

                    with st.expander("Preview"):
                        st.dataframe(df.head(3), use_container_width=True)

                    if st.button("✓ Upload", key=f"confirm_{slot_key}"):
                        with st.spinner("Uploading..."):
                            try:
                                uploaded_file.seek(0)
                                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                                resp = requests.post(f"{API_URL}/api/files/upload?category={slot_key}", files=files, timeout=60)
                                if resp.status_code == 200:
                                    st.session_state[f"uploaded_{slot_key}"] = True
                                    st.success(f"✅ Saved to {info['destination']}")
                                    st.balloons(); st.rerun()
                                else:
                                    st.error(f"❌ {resp.text}")
                            except Exception as e:
                                st.error(f"❌ {e}")
                except Exception as e:
                    st.error(f"Error: {e}")

            st.download_button(
                "⬇️ Template", data=",".join(info['required_cols'] + info['optional_cols']),
                file_name=f"{slot_key}_template.csv", mime="text/csv", key=f"tpl_{slot_key}"
            )

# ── Database status ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Database Status")

try:
    resp = requests.get(f"{API_URL}/api/database/status", timeout=5)
    status = resp.json() if resp.status_code == 200 else {}
except:
    status = {}

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("🦆 DuckDB")
        ddb = status.get("duckdb", {})
        st.metric("Tables", ddb.get("tables", 0))
        st.metric("Total Rows", f"{ddb.get('total_rows', 0):,}")

with col2:
    with st.container(border=True):
        st.subheader("🔗 FalkorDB")
        fdb = status.get("falkordb", {})
        st.metric("Nodes", f"{fdb.get('nodes', 0):,}")
        st.metric("Relationships", f"{fdb.get('relationships', 0):,}")

col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("🔄 Refresh Status"):
        st.rerun()

with col_c:
    st.markdown("")  # spacer

# ── Reset section ─────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🗑️ Data Management")

with st.expander("⚠️ Reset All Data", expanded=False):
    st.warning("This will **permanently delete** all uploaded data from DuckDB and FalkorDB. You'll need to re-upload your files.")
    confirm = st.checkbox("I understand — wipe everything", key="confirm_reset")
    if confirm:
        if st.button("🗑️ Reset All Data Now", type="primary"):
            with st.spinner("Wiping all data..."):
                try:
                    resp = requests.post(f"{API_URL}/api/database/reset", timeout=15)
                    if resp.status_code == 200:
                        result = resp.json()
                        # Clear upload tracking in session state
                        for k in FILE_SLOTS:
                            st.session_state[f"uploaded_{k}"] = False
                        st.success("✅ " + result.get("message", "All data wiped!"))
                        st.json(result.get("details", {}))
                        st.rerun()
                    else:
                        st.error(f"Reset failed: {resp.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("Check the box above to enable the reset button.")
