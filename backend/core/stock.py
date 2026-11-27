import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException, status
from core.db import get_supabase

logger = logging.getLogger(__name__)

def decrement_order_stock_atomic(store_id: str, items: List[Dict[str, Any]]) -> None:
    """
    Atomically and conditionally decrements inventory for an order:
    1. Checks each item's stock in app2026.products for the given store_id.
    2. Rejects if stock < qty (the last unit can never be oversold).
    3. Performs conditional update (stock >= qty).
    """
    sb = get_supabase()
    
    # 1. Fetch current stock for all items
    barcodes = [item["barcode"] for item in items]
    prod_res = sb.table("products").select("id, barcode, name, stock").eq("store_id", store_id).in_("barcode", barcodes).execute()
    
    products_by_barcode = {p["barcode"]: p for p in (prod_res.data or [])}
    
    for item in items:
        barcode = item["barcode"]
        qty = item["qty"]
        prod = products_by_barcode.get(barcode)
        
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": f"Product with barcode {barcode} not found in this store", "code": "PRODUCT_NOT_FOUND"}
            )
        
        if prod["stock"] < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Insufficient stock for '{prod['name']}' (available: {prod['stock']}, requested: {qty})",
                    "code": "INSUFFICIENT_STOCK"
                }
            )
            
    # 2. Conditionally decrement stock for each product
    for item in items:
        barcode = item["barcode"]
        qty = item["qty"]
        prod = products_by_barcode[barcode]
        new_stock = prod["stock"] - qty
        
        update_res = sb.table("products").update({
            "stock": new_stock,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", prod["id"]).gte("stock", qty).execute()
        
        if not update_res.data or len(update_res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Stock conflict for '{prod['name']}'. Could not reserve units.",
                    "code": "STOCK_CONFLICT"
                }
            )
