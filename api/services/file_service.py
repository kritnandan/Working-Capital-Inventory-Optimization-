"""
FileService - Handles file validation, quality checks, and storage
"""

import pandas as pd
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class FileService:
    """Service for file validation, quality checks, and storage management"""
    
    def __init__(self, storage_path: str = "/storage/uploads"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
    def validate_file(self, file_path: str, file_category: str) -> Dict[str, Any]:
        """Validate uploaded file against schema requirements"""
        schemas = {
            "sales": {
                "required": ["date", "sku", "quantity", "revenue"],
                "optional": ["customer_name", "region", "category"],
                "types": {"date": "datetime", "sku": "str", "quantity": "int", "revenue": "float"}
            },
            "inventory": {
                "required": ["sku", "qty_on_hand", "reorder_point"],
                "optional": ["location", "unit_cost", "supplier_id"],
                "types": {"sku": "str", "qty_on_hand": "int", "reorder_point": "int"}
            },
            "suppliers": {
                "required": ["supplier_id", "supplier_name", "lead_time"],
                "optional": ["contact_email", "rating", "country"],
                "types": {"supplier_id": "str", "lead_time": "int"}
            },
            "purchase_orders": {
                "required": ["po_number", "sku", "quantity"],
                "optional": ["order_date", "delivery_date", "supplier_id"],
                "types": {"po_number": "str", "quantity": "int"}
            }
        }
        
        schema = schemas.get(file_category, {})
        required_cols = schema.get("required", [])
        
        # Read file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # Check required columns
        missing_cols = set(required_cols) - set(df.columns)
        
        return {
            "valid": len(missing_cols) == 0,
            "file_category": file_category,
            "columns_found": list(df.columns),
            "columns_required": required_cols,
            "columns_missing": list(missing_cols),
            "row_count": len(df),
            "file_size_bytes": os.path.getsize(file_path)
        }
    
    def check_quality(self, file_path: str) -> Dict[str, Any]:
        """Check data quality issues in file"""
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        issues = []
        
        # Check for duplicates
        dupes = df.duplicated().sum()
        if dupes > 0:
            issues.append({"type": "duplicates", "count": int(dupes), "severity": "warning"})
        
        # Check for nulls
        nulls = df.isnull().sum().sum()
        if nulls > 0:
            issues.append({"type": "missing_values", "count": int(nulls), "severity": "warning"})
        
        # Check for negative quantities
        if 'quantity' in df.columns:
            negs = (df['quantity'] < 0).sum()
            if negs > 0:
                issues.append({"type": "negative_values", "count": int(negs), "severity": "error"})
        
        # Calculate quality score
        base_score = 100
        for issue in issues:
            if issue["severity"] == "error":
                base_score -= 10
            else:
                base_score -= 5
        
        return {
            "quality_score": max(0, base_score),
            "issues": issues,
            "total_rows": len(df),
            "columns": len(df.columns)
        }
    
    def store_file(self, file_path: str, file_category: str, metadata: Dict) -> str:
        """Store file and return storage path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{file_category}_{timestamp}.parquet"
        
        # Convert to parquet for storage
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        storage_path = os.path.join(self.storage_path, filename)
        df.to_parquet(storage_path)
        
        return storage_path
    
    def get_template(self, file_category: str) -> Dict[str, List[str]]:
        """Get template schema for file category"""
        templates = {
            "sales": {
                "required": ["date", "sku", "quantity", "revenue"],
                "optional": ["customer_name", "region", "category"],
                "example": {"date": "2024-01-01", "sku": "SKU001", "quantity": 100, "revenue": 5000.00}
            },
            "inventory": {
                "required": ["sku", "qty_on_hand", "reorder_point"],
                "optional": ["location", "unit_cost", "supplier_id"],
                "example": {"sku": "SKU001", "qty_on_hand": 500, "reorder_point": 100}
            },
            "suppliers": {
                "required": ["supplier_id", "supplier_name", "lead_time"],
                "optional": ["contact_email", "rating", "country"],
                "example": {"supplier_id": "SUP001", "supplier_name": "Acme Corp", "lead_time": 14}
            },
            "purchase_orders": {
                "required": ["po_number", "sku", "quantity"],
                "optional": ["order_date", "delivery_date", "supplier_id"],
                "example": {"po_number": "PO001", "sku": "SKU001", "quantity": 1000}
            }
        }
        return templates.get(file_category, {})
