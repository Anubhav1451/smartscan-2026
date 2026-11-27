import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.auth import get_optional_user, UserProfile
from models.schemas import (
    ExitVerifyRequest,
    ExitVerifyResponse,
    ExitUseRequest,
    ExitUseResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exit", tags=["Exit Verification"])

@router.post("/verify", response_model=ExitVerifyResponse)
def verify_exit_bill(
    req: ExitVerifyRequest,
    user: Optional[UserProfile] = Depends(get_optional_user)
):
    """
    Verifies bill authenticity for exit gate:
    - VERIFIED: genuine paid bill, not yet used
    - ALREADY_USED: genuine bill, but already exited
    - INVALID: fake or unrecognized bill number
    - UNPAID: checkout created but unpaid
    Records every verification attempt in app2026.exit_verifications.
    """
    sb = get_supabase()
    bill_no = (req.bill_no or req.bill_id or "").strip().upper()
    if not bill_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bill_no or bill_id is required", "code": "MISSING_BILL_NO"}
        )
    verified_by = user.id if user else None
    
    # 1. Look up order by bill_no
    res = sb.table("orders").select(
        "id, bill_no, store_id, total, payment_status, status, paid_at, stores(id, name, code, area)"
    ).eq("bill_no", bill_no).execute()
    
    if not res.data or len(res.data) == 0:
        # Unknown/fake bill
        sb.table("exit_verifications").insert({
            "bill_no": bill_no,
            "result": "INVALID",
            "verified_by": verified_by,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return ExitVerifyResponse(
            result="INVALID",
            bill_no=bill_no,
            message="Invalid or unrecognized bill number"
        )
        
    order = res.data[0]
    order_id = order["id"]
    
    # 2. Check if already used
    if order["status"] == "USED":
        sb.table("exit_verifications").insert({
            "order_id": order_id,
            "bill_no": bill_no,
            "result": "ALREADY_USED",
            "verified_by": verified_by,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return ExitVerifyResponse(
            result="ALREADY_USED",
            bill_no=bill_no,
            order_id=order_id,
            message="This bill has already been verified and used for exit"
        )
        
    # 3. Check payment status
    if order["payment_status"] != "PAID":
        sb.table("exit_verifications").insert({
            "order_id": order_id,
            "bill_no": bill_no,
            "result": "UNPAID",
            "verified_by": verified_by,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return ExitVerifyResponse(
            result="UNPAID",
            bill_no=bill_no,
            order_id=order_id,
            message="This order is not yet paid"
        )
        
    # 4. Genuine, verified paid bill
    sb.table("exit_verifications").insert({
        "order_id": order_id,
        "bill_no": bill_no,
        "result": "VERIFIED",
        "verified_by": verified_by,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    items_res = sb.table("order_items").select("barcode, name, price, qty").eq("order_id", order_id).execute()
    store_info = order.get("stores") or {}
    
    return ExitVerifyResponse(
        result="VERIFIED",
        bill_no=bill_no,
        order_id=order_id,
        store_name=store_info.get("name"),
        store_code=store_info.get("code"),
        total=order["total"],
        paid_at=order.get("paid_at"),
        items=items_res.data or [],
        message="Valid paid bill verified. Clear for exit."
    )

@router.post("/use", response_model=ExitUseResponse)
def mark_bill_used(
    req: ExitUseRequest,
    user: Optional[UserProfile] = Depends(get_optional_user)
):
    """Marks a verified bill as USED upon shopper exit."""
    sb = get_supabase()
    bill_no = (req.bill_no or req.bill_id or "").strip().upper()
    if not bill_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bill_no or bill_id is required", "code": "MISSING_BILL_NO"}
        )
    verified_by = user.id if user else None
    
    res = sb.table("orders").select("id, status, payment_status").eq("bill_no", bill_no).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Bill not found", "code": "BILL_NOT_FOUND"}
        )
    order = res.data[0]
    
    if order["status"] == "USED":
        return ExitUseResponse(
            status="ALREADY_USED",
            bill_no=bill_no,
            message="Bill was already marked as used"
        )
        
    if order["payment_status"] != "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Cannot exit with an unpaid order", "code": "UNPAID_ORDER"}
        )
        
    sb.table("orders").update({
        "status": "USED"
    }).eq("id", order["id"]).execute()
    
    sb.table("exit_verifications").insert({
        "order_id": order["id"],
        "bill_no": bill_no,
        "result": "USED",
        "verified_by": verified_by,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    return ExitUseResponse(
        status="USED",
        bill_no=bill_no,
        message="Exit recorded. Customer cleared to leave."
    )
