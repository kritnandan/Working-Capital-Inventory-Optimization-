"""
FalkorDBService - Handles graph queries, relationship sync, and Cypher operations
"""

from falkordb import FalkorDB
from typing import Dict, List, Any, Optional
import os

class FalkorDBService:
    """Service for FalkorDB graph operations and supplier network analysis"""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or os.getenv("FALKORDB_HOST", "falkordb")
        self.port = port or int(os.getenv("FALKORDB_PORT", 6379))
        self.graph_name = "supply_chain"
    
    def _get_graph(self):
        """Get FalkorDB graph connection — raises if unavailable"""
        try:
            db = FalkorDB(host=self.host, port=self.port)
            return db.select_graph(self.graph_name)
        except Exception as e:
            raise ConnectionError(f"FalkorDB unavailable at {self.host}:{self.port}: {e}")

    def get_supplier_network(self) -> List[Dict[str, Any]]:
        """Get full supplier-to-product mapping graph"""
        try:
            graph = self._get_graph()
        except ConnectionError:
            return []
        
        query = """
        MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)
        RETURN s.supplier_id, s.supplier_name, p.sku, p.product_name
        ORDER BY s.supplier_name
        """
        
        result = graph.query(query)
        return [
            {
                "supplier_id": row[0],
                "supplier_name": row[1], 
                "sku": row[2],
                "product_name": row[3]
            }
            for row in result.result_set
        ]
    
    def find_single_source_risks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Find products with only one supplier (single source risk)"""
        graph = self._get_graph()
        
        query = f"""
        MATCH (p:Product)<-[:SUPPLIES]-(s:Supplier)
        WITH p, COUNT(s) as supplier_count, COLLECT(s) as suppliers
        WHERE supplier_count = 1
        RETURN p.sku, p.product_name, suppliers[0].supplier_id, suppliers[0].supplier_name
        ORDER BY p.annual_revenue DESC
        LIMIT {limit}
        """
        
        result = graph.query(query)
        return [
            {
                "sku": row[0],
                "product": row[1],
                "sole_supplier_id": row[2],
                "sole_supplier_name": row[3],
                "risk_level": "high"
            }
            for row in result.result_set
        ]
    
    def ripple_effect_analysis(self, supplier_id: str) -> Dict[str, Any]:
        """Trace impact of a supplier failure through the network"""
        graph = self._get_graph()
        
        # Find all products affected
        query = f"""
        MATCH (s:Supplier {{supplier_id: '{supplier_id}'}})-[:SUPPLIES]->(p:Product)
        OPTIONAL MATCH (p)-[:COMPONENT_OF]->(finished:Product)
        RETURN s.supplier_name, p.sku, p.product_name, finished.sku as finished_sku, finished.product_name as finished_product
        """
        
        result = graph.query(query)
        
        impacted_products = []
        revenue_at_risk = 0
        
        for row in result.result_set:
            impacted_products.append({
                "sku": row[1],
                "product": row[2],
                "finished_good_sku": row[3],
                "finished_good": row[4]
            })
            revenue_at_risk += 100000  # Placeholder
        
        return {
            "failed_supplier_id": supplier_id,
            "failed_supplier_name": result.result_set[0][0] if result.result_set else "Unknown",
            "impacted_products": impacted_products,
            "total_impacted": len(impacted_products),
            "estimated_revenue_at_risk": revenue_at_risk,
            "severity": "high" if len(impacted_products) > 10 else "medium"
        }
    
    def get_lead_time_variability(self) -> List[Dict[str, Any]]:
        """Get lead time statistics per supplier"""
        graph = self._get_graph()
        
        query = """
        MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)
        WITH s, COUNT(p) as product_count, AVG(p.lead_time) as avg_lead, 
             MIN(p.lead_time) as min_lead, MAX(p.lead_time) as max_lead,
             stdev(p.lead_time) as std_lead
        RETURN s.supplier_id, s.supplier_name, product_count, avg_lead, min_lead, max_lead, std_lead
        ORDER BY std_lead DESC
        """
        
        result = graph.query(query)
        return [
            {
                "supplier_id": row[0],
                "supplier_name": row[1],
                "product_count": row[2],
                "avg_lead_time": round(row[3], 1) if row[3] else 0,
                "min_lead_time": row[4],
                "max_lead_time": row[5],
                "variability": round(row[6], 2) if row[6] else 0
            }
            for row in result.result_set
        ]
    
    def find_alternative_suppliers(self, sku: str) -> Dict[str, Any]:
        """Find backup suppliers for a given SKU"""
        graph = self._get_graph()
        
        # Get current supplier
        current_query = f"""
        MATCH (s:Supplier)-[:SUPPLIES]->(p:Product {{sku: '{sku}'}})
        RETURN s.supplier_id, s.supplier_name, s.lead_time, s.rating
        """
        current_result = graph.query(current_query)
        current = None
        if current_result.result_set:
            current = {
                "supplier_id": current_result.result_set[0][0],
                "supplier_name": current_result.result_set[0][1],
                "lead_time": current_result.result_set[0][2],
                "rating": current_result.result_set[0][3]
            }
        
        # Find alternatives (suppliers with similar products)
        alt_query = f"""
        MATCH (p:Product {{sku: '{sku}'}})-[:CATEGORY]->(cat:Category)<-[:CATEGORY]-(alt_product:Product)
        MATCH (alt_supplier:Supplier)-[:SUPPLIES]->(alt_product)
        WHERE NOT (alt_supplier)-[:SUPPLIES]->(p)
        RETURN DISTINCT alt_supplier.supplier_id, alt_supplier.supplier_name, 
               alt_supplier.lead_time, alt_supplier.rating, alt_supplier.country
        ORDER BY alt_supplier.rating DESC, alt_supplier.lead_time ASC
        LIMIT 5
        """
        alt_result = graph.query(alt_query)
        
        alternatives = [
            {
                "supplier_id": row[0],
                "supplier_name": row[1],
                "lead_time": row[2],
                "rating": row[3],
                "country": row[4]
            }
            for row in alt_result.result_set
        ]
        
        return {
            "sku": sku,
            "current_supplier": current,
            "alternatives": alternatives,
            "alternative_count": len(alternatives)
        }
    
    def sync_relationships(self, table_data: str, relationship_type: str) -> bool:
        """Sync relationships from DuckDB data to graph"""
        # Placeholder for relationship sync logic
        return True
    
    def create_graph_schema(self) -> bool:
        """Initialize graph schema with constraints and indices"""
        graph = self._get_graph()
        
        # Create indices
        indices = [
            "CREATE INDEX ON :Supplier(supplier_id)",
            "CREATE INDEX ON :Product(sku)",
            "CREATE INDEX ON :PurchaseOrder(po_number)"
        ]
        
        for idx in indices:
            try:
                graph.query(idx)
            except:
                pass  # Index may already exist
        
        return True
