from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.auth import get_current_user, UserProfile, require_manager
from models.schemas import ProductResponse

router = APIRouter(prefix="/manager", tags=["Manager"])

def verify_manager_store_access(user: UserProfile, store_id: str):
    """Enforces manager store isolation: a manager cannot manage another store."""
    if user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access forbidden: manager role required", "code": "FORBIDDEN"}
        )
    if user.store_id and str(user.store_id) != str(store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access forbidden: you can only manage your assigned store", "code": "STORE_ISOLATION_FORBIDDEN"}
        )

@router.get("/stores/{store_id}/products", response_model=List[ProductResponse])
def get_manager_store_products(store_id: str, user: UserProfile = Depends(get_current_user)):
    """Retrieve store catalogue with manager isolation check."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    res = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id).order("name").execute()
    return res.data or []

@router.get("/stores/{store_id}/dashboard")
def get_manager_store_dashboard(store_id: str, user: UserProfile = Depends(get_current_user)):
    """Retrieve manager dashboard KPIs with manager isolation check."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    
    # Store info
    store_res = sb.table("stores").select("id, name, code, area").eq("id", store_id).execute()
    store = store_res.data[0] if store_res.data else {}
    
    # Orders aggregate
    orders_res = sb.table("orders").select("id, total, payment_status, status, created_at").eq("store_id", store_id).execute()
    orders = orders_res.data or []
    
    paid_orders = [o for o in orders if o["payment_status"] == "PAID"]
    total_revenue = sum(o["total"] for o in paid_orders)
    queue_time_saved_minutes = len(paid_orders) * 4 # SDG metric: ~4 min saved per Scan-and-Go shopper
    paper_bills_saved = len(paid_orders)
    
    # Products aggregate
    prods_res = sb.table("products").select("id, stock").eq("store_id", store_id).execute()
    products = prods_res.data or []
    low_stock_count = sum(1 for p in products if p["stock"] <= 5)
    
    # Unknown scans count
    unk_res = sb.table("unknown_scans").select("id, count").eq("store_id", store_id).execute()
    unknown_scans_count = sum(u["count"] for u in (unk_res.data or []))
    
    return {
        "store": store,
        "kpis": {
            "total_revenue": total_revenue,
            "total_orders": len(orders),
            "paid_orders": len(paid_orders),
            "queue_time_saved_minutes": queue_time_saved_minutes,
            "paper_bills_saved": paper_bills_saved,
            "low_stock_count": low_stock_count,
            "unknown_scans_count": unknown_scans_count
        }
    }

@router.get("/stores/{store_id}/unknown-scans")
def get_manager_unknown_scans(store_id: str, user: UserProfile = Depends(get_current_user)):
    """Retrieve logged unknown customer scans for store catalogue review."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    res = sb.table("unknown_scans").select("id, store_id, barcode, count, first_seen_at, last_seen_at").eq("store_id", store_id).order("last_seen_at", desc=True).execute()
    return res.data or []
