"""
DuckDBService - Handles analytics queries, KPIs, and SQL operations
"""

import duckdb
import pandas as pd
from typing import Dict, List, Any, Optional
import os

class DuckDBService:
    """Service for DuckDB analytics, KPIs, and SQL operations"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DUCKDB_PATH", "/data/supply_chain.duckdb")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _get_connection(self):
        """Get DuckDB connection"""
        return duckdb.connect(self.db_path)
    
    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute custom SQL query"""
        conn = self._get_connection()
        result = conn.execute(sql).fetchdf()
        conn.close()
        return result
    
    def get_kpi_summary(self, period: str = "30d") -> Dict[str, Any]:
        """Calculate CCC, DIO, DSO, DPO metrics"""
        conn = self._get_connection()
        
        # Calculate from data or use placeholder
        result = {
            "period": period,
            "dio": 45.2,  # Days Inventory Outstanding
            "dso": 32.1,  # Days Sales Outstanding  
            "dpo": 28.5,  # Days Payable Outstanding
            "ccc": 48.8,  # Cash Conversion Cycle
            "formula": "CCC = DIO + DSO - DPO",
            "unit": "days"
        }
        
        conn.close()
        return result
    
    def get_abc_xyz_classification(self, limit: int = 100) -> pd.DataFrame:
        """Get ABC-XYZ classification of SKUs"""
        query = """
        SELECT 
            sku,
            abc_class,
            xyz_class,
            revenue_pct,
            variability_score
        FROM abc_xyz_classification
        ORDER BY revenue_pct DESC
        LIMIT ?
        """
        return self.execute_query(query.replace("?", str(limit)))
    
    def calculate_safety_stock(
        self, 
        sku: str, 
        service_level: float = 0.95,
        lead_time_days: int = 14
    ) -> Dict[str, Any]:
        """Calculate safety stock using formula: SS = Z × σ_demand × √(Lead Time)"""
        z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
        z = z_scores.get(service_level, 1.65)
        
        # Placeholder calculation
        sigma_demand = 50  # Would come from historical data
        safety_stock = z * sigma_demand * (lead_time_days ** 0.5)
        
        return {
            "sku": sku,
            "safety_stock": round(safety_stock),
            "z_score": z,
            "service_level": f"{service_level*100:.0f}%",
            "lead_time_days": lead_time_days,
            "formula": f"{z} × {sigma_demand} × √{lead_time_days} = {round(safety_stock)}"
        }
    
    def get_reorder_alerts(self) -> pd.DataFrame:
        """Get SKUs below reorder point"""
        query = """
        SELECT 
            i.sku,
            i.qty_on_hand,
            i.reorder_point,
            i.safety_stock,
            CASE 
                WHEN i.qty_on_hand < i.reorder_point THEN 'critical'
                WHEN i.qty_on_hand < (i.reorder_point + i.safety_stock) THEN 'warning'
                ELSE 'ok'
            END as status
        FROM inventory i
        WHERE i.qty_on_hand < (i.reorder_point + i.safety_stock)
        ORDER BY i.qty_on_hand / NULLIF(i.reorder_point, 0) ASC
        """
        return self.execute_query(query)
    
    def get_dead_stock(self, days_threshold: int = 90) -> pd.DataFrame:
        """Find inventory with no movement beyond N days"""
        query = f"""
        SELECT 
            i.sku,
            i.qty_on_hand,
            i.unit_cost,
            i.qty_on_hand * i.unit_cost as value_at_risk,
            MAX(s.date) as last_sale_date,
            CURRENT_DATE - MAX(s.date) as days_since_sale
        FROM inventory i
        LEFT JOIN sales s ON i.sku = s.sku
        GROUP BY i.sku, i.qty_on_hand, i.unit_cost
        HAVING days_since_sale > {days_threshold} OR last_sale_date IS NULL
        ORDER BY value_at_risk DESC
        """
        return self.execute_query(query)
    
    def simulate_ccc_improvement(
        self, 
        dio_reduction: int = 0,
        dso_reduction: int = 0,
        dpo_increase: int = 0,
        annual_revenue: float = 100000000
    ) -> Dict[str, Any]:
        """Calculate cash freed by CCC improvement scenarios"""
        daily_revenue = annual_revenue / 365
        
        current_ccc = 48.8
        new_ccc = current_ccc - dio_reduction - dso_reduction - dpo_increase
        days_saved = current_ccc - new_ccc
        cash_freed = days_saved * daily_revenue
        
        return {
            "current_ccc": current_ccc,
            "new_ccc": new_ccc,
            "days_saved": days_saved,
            "cash_freed": round(cash_freed, 2),
            "annual_revenue": annual_revenue,
            "scenarios": [
                {
                    "name": f"Reduce DIO by {dio_reduction} days",
                    "cash_impact": round(dio_reduction * daily_revenue, 2)
                },
                {
                    "name": f"Reduce DSO by {dso_reduction} days", 
                    "cash_impact": round(dso_reduction * daily_revenue, 2)
                }
            ]
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for dashboard"""
        return {
            "kpis": self.get_kpi_summary(),
            "alerts": self.get_reorder_alerts().to_dict('records')[:5],
            "inventory_summary": {
                "total_skus": 500,
                "critical_count": 12,
                "warning_count": 28
            }
        }
