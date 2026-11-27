from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.rate_limit import check_scan_rate_limit
from models.schemas import ScanRequest, ProductResponse

router = APIRouter(tags=["Scan"])

@router.post("/scan", response_model=ProductResponse)
def scan_product(req: ScanRequest, _rl: None = Depends(check_scan_rate_limit)):
    """
    Looks up a product within the given store by barcode.
    On a miss, logs the barcode to the store's unknown_scans queue and returns 404.
    """
    return do_scan_lookup(store_id=req.store_id, barcode=req.barcode)

@router.get("/products/by-barcode", response_model=ProductResponse)
def scan_product_get(store_id: str, barcode: str):
    """GET alias for scan lookup."""
    return do_scan_lookup(store_id=store_id, barcode=barcode)

def do_scan_lookup(store_id: str, barcode: str):
    sb = get_supabase()
    
    # Check if product exists in this store
    res = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id).eq("barcode", barcode).execute()
    
    if res.data and len(res.data) > 0:
        return res.data[0]
    
    # On miss: log to app2026.unknown_scans in DB
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        unk_res = sb.table("unknown_scans").select("id, count").eq("store_id", store_id).eq("barcode", barcode).execute()
        if unk_res.data and len(unk_res.data) > 0:
            existing = unk_res.data[0]
            sb.table("unknown_scans").update({
                "count": existing["count"] + 1,
                "last_seen_at": now_iso
            }).eq("id", existing["id"]).execute()
        else:
            sb.table("unknown_scans").insert({
                "store_id": store_id,
                "barcode": barcode,
                "count": 1,
                "first_seen_at": now_iso,
                "last_seen_at": now_iso
            }).execute()
    except Exception:
        pass
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": f"Product with barcode '{barcode}' is not found in this store", "code": "PRODUCT_NOT_FOUND"}
    )
