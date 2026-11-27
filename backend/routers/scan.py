from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from core.db import get_supabase
from models.schemas import ScanRequest, ProductResponse

router = APIRouter(tags=["Scan"])

@router.post("/scan", response_model=ProductResponse)
def scan_product(req: ScanRequest):
    """
    Looks up a product within the given store by barcode.
    On a miss, logs the barcode to the store's unknown_scans queue and returns 404.
    """
    sb = get_supabase()
    
    # Check if product exists in this store
    res = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", req.store_id).eq("barcode", req.barcode).execute()
    
    if res.data and len(res.data) > 0:
        return res.data[0]
    
    # On miss: log to app2026.unknown_scans in DB
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        # Check existing unknown scan entry
        unk_res = sb.table("unknown_scans").select("id, count").eq("store_id", req.store_id).eq("barcode", req.barcode).execute()
        if unk_res.data and len(unk_res.data) > 0:
            existing = unk_res.data[0]
            sb.table("unknown_scans").update({
                "count": existing["count"] + 1,
                "last_seen_at": now_iso
            }).eq("id", existing["id"]).execute()
        else:
            sb.table("unknown_scans").insert({
                "store_id": req.store_id,
                "barcode": req.barcode,
                "count": 1,
                "first_seen_at": now_iso,
                "last_seen_at": now_iso
            }).execute()
    except Exception:
        # Do not fail request if logging unknown scan fails
        pass
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": f"Product with barcode '{req.barcode}' is not found in this store", "code": "PRODUCT_NOT_FOUND"}
    )
