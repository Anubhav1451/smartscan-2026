from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.auth import get_current_user, UserProfile, require_staff_or_manager
from routers.orders import confirm_cash_payment
from models.schemas import CashConfirmResponse

router = APIRouter(prefix="/staff", tags=["Exit Staff"])

@router.get("/cash-pending")
def list_cash_pending_orders(user: UserProfile = Depends(get_current_user)):
    """List orders waiting for cash confirmation at the exit counter."""
    sb = get_supabase()
    query = sb.table("orders").select(
        "id, store_id, customer_id, total, payment_method, payment_status, status, created_at, stores(id, name, code, area)"
    ).eq("payment_status", "CASH_PENDING")
    
    if user.store_id:
        query = query.eq("store_id", user.store_id)
        
    res = query.order("created_at", desc=True).execute()
    orders = res.data or []
    
    for ord_obj in orders:
        items_res = sb.table("order_items").select("id, barcode, name, price, qty").eq("order_id", ord_obj["id"]).execute()
        ord_obj["items"] = items_res.data or []
        
    return orders

@router.post("/orders/{order_id}/confirm-cash", response_model=CashConfirmResponse)
def staff_confirm_cash(order_id: str, user: UserProfile = Depends(require_staff_or_manager)):
    """Staff endpoint to confirm cash and activate bill."""
    return confirm_cash_payment(order_id=order_id, user=user)
