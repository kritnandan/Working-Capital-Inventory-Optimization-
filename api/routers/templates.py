"""
Templates API - Returns file templates and schema definitions
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Any
from services.file_service import FileService

router = APIRouter()
file_service = FileService()

class TemplateResponse(BaseModel):
    file_category: str
    required_columns: List[str]
    optional_columns: List[str]
    example: Dict[str, Any]
    description: str

@router.get("/{category}", response_model=TemplateResponse)
async def get_template(category: str):
    """Get template schema for a file category"""
    template = file_service.get_template(category)
    
    descriptions = {
        "sales": "Daily sales transactions for demand analysis and revenue tracking",
        "inventory": "Current stock levels, reorder points, and safety stock by SKU",
        "suppliers": "Supplier master data with lead times and contact information",
        "purchase_orders": "Purchase order transactions linking suppliers to products"
    }
    
    return TemplateResponse(
        file_category=category,
        required_columns=template.get("required", []),
        optional_columns=template.get("optional", []),
        example=template.get("example", {}),
        description=descriptions.get(category, "")
    )

@router.get("/")
async def get_all_templates():
    """Get all available templates"""
    categories = ["sales", "inventory", "suppliers", "purchase_orders"]
    return {
        "templates": [
            {
                "category": cat,
                "template": file_service.get_template(cat)
            }
            for cat in categories
        ]
    }
