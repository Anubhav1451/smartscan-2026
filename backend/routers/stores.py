from typing import List
from fastapi import APIRouter, HTTPException, status
from core.db import get_supabase
from models.schemas import StoreResponse, ProductResponse

router = APIRouter(tags=["Stores"])

@router.get("/stores", response_model=List[StoreResponse])
def list_stores():
    """List all active stores from app2026 schema."""
    sb = get_supabase()
    res = sb.table("stores").select("id, retailer_id, name, code, area, address, is_active").eq("is_active", True).order("name").execute()
    return res.data or []

@router.get("/stores/{store_id}/products", response_model=List[ProductResponse])
def list_store_products(store_id: str):
    """List products for a specific store."""
    sb = get_supabase()
    res = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id).order("name").execute()
    return res.data or []
